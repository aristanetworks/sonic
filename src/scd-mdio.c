/* Copyright (c) 2019 Arista Networks, Inc.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 */

#include <linux/cdev.h>
#include <linux/fs.h>
#include <linux/idr.h>
#include <linux/module.h>
#include <linux/pci.h>
#include <linux/version.h>

#include "scd.h"
#include "scd-hwmon.h"
#include "scd-mdio.h"

#define SCD_MDIO_CDEV_MAX_DEVICES 256

#define SCD_MDIO_PPOS_PRTAD_OVR   BIT(27)
#define SCD_MDIO_PPOS_DEVAD_OVR   BIT(26)
#define SCD_MDIO_PPOS_PRTAD_SHIFT 21
#define SCD_MDIO_PPOS_DEVAD_SHIFT 16
#define SCD_MDIO_PPOS_MAX         0x0fffffff

static dev_t scd_mdio_devt;
static struct class *scd_mdio_cdev_class;
static DEFINE_IDA(scd_mdio_ida);
static int scd_mdio_cdev_refcount;
static DEFINE_MUTEX(scd_mdio_cdev_mutex);

static int scd_mdio_cdev_init(void);
static void scd_mdio_cdev_deinit(void);

static void mdio_master_lock(struct scd_mdio_master *master)
{
   mutex_lock(&master->mutex);
}

static void mdio_master_unlock(struct scd_mdio_master *master)
{
   mutex_unlock(&master->mutex);
}

/* MDIO bus functions */
static union mdio_ctrl_status_reg mdio_master_read_cs(struct scd_mdio_master *master)
{
   union mdio_ctrl_status_reg cs;

   cs.reg = scd_read_register(master->ctx->dev, master->cs);
   return cs;
}

static void mdio_master_write_cs(struct scd_mdio_master *master,
                                 union mdio_ctrl_status_reg cs)
{
   scd_write_register(master->ctx->dev, master->cs, cs.reg);
}

static union mdio_ctrl_status_reg get_default_mdio_cs(struct scd_mdio_master *master)
{
   union mdio_ctrl_status_reg cs = {0};

   cs.sp = master->speed;
   return cs;
}

static void mdio_master_reset(struct scd_mdio_master *master)
{
   union mdio_ctrl_status_reg cs = get_default_mdio_cs(master);

   cs.reset = 1;
   mdio_master_write_cs(master, cs);
   msleep(MDIO_RESET_DELAY);

   cs.reset = 0;
   mdio_master_write_cs(master, cs);
   msleep(MDIO_RESET_DELAY);
}

static void mdio_master_reset_interrupt(struct scd_mdio_master *master)
{
   union mdio_ctrl_status_reg cs = get_default_mdio_cs(master);

   cs.fe = 1;
   mdio_master_write_cs(master, cs);
}

static int mdio_master_wait_response(struct scd_mdio_master *master)
{
   union mdio_ctrl_status_reg cs;
   unsigned long delay = MDIO_WAIT_INITIAL;

   while (!MDIO_WAIT_END(delay)) {
      cs = mdio_master_read_cs(master);
      if (cs.res_count == 1) {
         return 0;
      } else if (cs.res_count == 0) {
         if (delay < MDIO_WAIT_MAX_UDELAY)
            udelay(delay);
         else
            msleep(delay / 1000);

         delay = MDIO_WAIT_NEXT(delay);
      } else {
         dev_warn(get_scd_dev(master->ctx), "mdio wait_resp failed on master %d",
                  master->id);
         return -EOPNOTSUPP;
      }
   }

   dev_warn(get_scd_dev(master->ctx), "mdio wait_resp timeout on master %d",
            master->id);

   return -EAGAIN;
}

static u8 mdio_master_get_req_id(struct scd_mdio_master *master)
{
   return master->req_id++;
}

static s32 scd_mdio_bus_request(struct scd_mdio_bus *mdio_bus,
                                enum mdio_operation op, int clause,
                                int prtad, int devad, u16 data)
{
   struct scd_mdio_master *master = mdio_bus->master;
   union mdio_request_lo_reg req_lo = {0};
   union mdio_request_hi_reg req_hi = {0};
   union mdio_response_reg resp = {0};
   int err;

   mdio_master_reset_interrupt(master);

   req_lo.bs = mdio_bus->id;
   req_lo.t = clause;
   req_lo.op = op;
   req_lo.dt = devad;
   req_lo.pa = prtad;
   req_lo.d = data;
   scd_write_register(master->ctx->dev, master->req_lo, req_lo.reg);

   req_hi.ri = mdio_master_get_req_id(master);
   scd_write_register(master->ctx->dev, master->req_hi, req_hi.reg);

   err = mdio_master_wait_response(master);
   if (err)
      return err;

   mdio_master_reset_interrupt(master);

   resp.reg = scd_read_register(master->ctx->dev, master->resp);
   if (resp.ts != 1 || resp.fe == 1) {
      dev_warn(get_scd_dev(master->ctx), "mdio bus request failed in reading resp");
      return -EIO;
   }

   if (op == SCD_MDIO_READ)
      return resp.d;

   return 0;
}

static s32 scd_mii_bus_do(struct mii_bus *mii_bus, int addr, int op, int regnum, u16 val)
{
   struct scd_mdio_bus *mdio_bus = mii_bus->priv;
   struct scd_context *ctx = mdio_bus->master->ctx;
   int full_addr = mdio_bus->dev_id_to_addr[addr];
   int prtad = (full_addr >> 5) & 0x1f;
   int devad = full_addr & 0x1f;
   int clause = (full_addr & MDIO_PHY_ID_C45) ? 1 : 0;
   int err;

   dev_dbg(get_scd_dev(ctx), "mii_bus_do, op: %d, master: %d, bus: %d, clause %d, "
           "prtad: %d, devad: %d, regnum: %04x, value: %04x", op,
           mdio_bus->master->id, mdio_bus->id, clause, prtad, devad, regnum, val);

   mdio_master_lock(mdio_bus->master);

   err = scd_mdio_bus_request(mdio_bus, SCD_MDIO_SET, clause, prtad, devad, regnum);
   if (err)
      goto final;

   err = scd_mdio_bus_request(mdio_bus, op, clause, prtad, devad, val);

final:
   mdio_master_unlock(mdio_bus->master);
   return err;
}

static s32 scd_mii_bus_read(struct mii_bus *mii_bus, int addr, int regnum)
{
   return scd_mii_bus_do(mii_bus, addr, SCD_MDIO_READ, regnum, 0);
}

static s32 scd_mii_bus_write(struct mii_bus *mii_bus, int addr, int regnum,
                             u16 val)
{
   return scd_mii_bus_do(mii_bus, addr, SCD_MDIO_WRITE, regnum, val);
}

static int scd_mdio_mii_id(int prtad, int devad, int mode)
{
   int mii_id = (prtad << 5) | devad;

   if (mode & MDIO_SUPPORTS_C45)
      mii_id |= MDIO_PHY_ID_C45;

   return mii_id;
}

/* Netdev ioctl path (legacy) */
static int scd_mdio_read(struct net_device *netdev, int prtad, int devad, u16 addr)
{
   struct scd_mdio_device *mdio_dev = netdev_priv(netdev);
   struct scd_context *ctx = mdio_dev->mdio_bus->master->ctx;
   int dev_id = mdio_dev->id;
   int mii_id = scd_mdio_mii_id(prtad, devad, mdio_dev->mode_support);
   int i;

   for (i = 0; i < PHY_MAX_ADDR; i++) {
      if (mdio_dev->mdio_bus->dev_id_to_addr[i] == mii_id) {
         dev_id = i;
         break;
      }
   }

   dev_dbg(get_scd_dev(ctx),
           "scd_mdio_read, dev_id: %04x, prtad: %d, devad: %d, addr: %04x", dev_id,
           prtad, devad, addr);
   return mdiobus_read(mdio_dev->mdio_bus->mii_bus, dev_id, addr);
}

static int scd_mdio_write(struct net_device *netdev, int prtad, int devad, u16 addr,
                          u16 value)
{
   struct scd_mdio_device *mdio_dev = netdev_priv(netdev);
   struct scd_context *ctx = mdio_dev->mdio_bus->master->ctx;
   int dev_id = mdio_dev->id;
   int mii_id = scd_mdio_mii_id(prtad, devad, mdio_dev->mode_support);
   int i;

   for (i = 0; i < PHY_MAX_ADDR; i++) {
      if (mdio_dev->mdio_bus->dev_id_to_addr[i] == mii_id) {
         dev_id = i;
         break;
      }
   }

   dev_dbg(get_scd_dev(ctx),
           "scd_mdio_write, dev_id: %04x, prtad: %d, devad: %d, addr: %04x, "
           "value: %04x", dev_id, prtad, devad, addr, value);
   return mdiobus_write(mdio_dev->mdio_bus->mii_bus, dev_id, addr, value);
}

/* Char device file operations */
static int scd_mdio_cdev_open(struct inode *inode, struct file *filp)
{
   struct scd_mdio_device *dev = container_of(inode->i_cdev,
                                              struct scd_mdio_device, cdev);
   filp->private_data = dev;
   return 0;
}

static ssize_t scd_mdio_cdev_read(struct file *filp, char __user *buf,
                                  size_t count, loff_t *ppos)
{
   struct scd_mdio_device *dev = filp->private_data;
   struct scd_mdio_master *master = dev->mdio_bus->master;
   int clause = (dev->mode_support & MDIO_SUPPORTS_C45) ? 1 : 0;
   u16 prtad, devad, reg;
   u16 val;
   int ret;

   if (count < sizeof(val))
      return -EINVAL;
   if (*ppos > SCD_MDIO_PPOS_MAX)
      return -EINVAL;

   prtad = (*ppos & SCD_MDIO_PPOS_PRTAD_OVR) ?
           (*ppos >> SCD_MDIO_PPOS_PRTAD_SHIFT) & 0x1f : dev->prtad;
   devad = (*ppos & SCD_MDIO_PPOS_DEVAD_OVR) ?
           (*ppos >> SCD_MDIO_PPOS_DEVAD_SHIFT) & 0x1f : dev->devad;
   reg = *ppos & 0xffff;

   dev_dbg(get_scd_dev(master->ctx),
           "cdev_read_req, master: %d, bus: %d, dev_prtad: %d, dev_devad: %d, "
           "prtad: %d, devad: %d, reg: %04x",
           master->id, dev->mdio_bus->id, dev->prtad, dev->devad,
           prtad, devad, reg);

   mdio_master_lock(master);
   ret = scd_mdio_bus_request(dev->mdio_bus, SCD_MDIO_SET, clause,
                              prtad, devad, reg);
   if (!ret)
      ret = scd_mdio_bus_request(dev->mdio_bus, SCD_MDIO_READ, clause,
                                 prtad, devad, 0);
   mdio_master_unlock(master);

   if (ret < 0)
      return ret;

   val = ret;
   if (copy_to_user(buf, &val, sizeof(val)))
      return -EFAULT;

   dev_dbg(get_scd_dev(master->ctx),
           "cdev_read_ret, master: %d, bus: %d, prtad: %d, devad: %d, "
           "reg: %04x, val: %04x",
           master->id, dev->mdio_bus->id, prtad, devad, reg, val);

   return sizeof(val);
}

static ssize_t scd_mdio_cdev_write(struct file *filp, const char __user *buf,
                                   size_t count, loff_t *ppos)
{
   struct scd_mdio_device *dev = filp->private_data;
   struct scd_mdio_master *master = dev->mdio_bus->master;
   int clause = (dev->mode_support & MDIO_SUPPORTS_C45) ? 1 : 0;
   u16 prtad, devad, reg;
   u16 val;
   int ret;

   if (count < sizeof(val))
      return -EINVAL;
   if (*ppos > SCD_MDIO_PPOS_MAX)
      return -EINVAL;

   if (copy_from_user(&val, buf, sizeof(val)))
      return -EFAULT;

   prtad = (*ppos & SCD_MDIO_PPOS_PRTAD_OVR) ?
           (*ppos >> SCD_MDIO_PPOS_PRTAD_SHIFT) & 0x1f : dev->prtad;
   devad = (*ppos & SCD_MDIO_PPOS_DEVAD_OVR) ?
           (*ppos >> SCD_MDIO_PPOS_DEVAD_SHIFT) & 0x1f : dev->devad;
   reg = *ppos & 0xffff;

   dev_dbg(get_scd_dev(master->ctx),
           "cdev_write_req, master: %d, bus: %d, dev_prtad: %d, dev_devad: %d, "
           "prtad: %d, devad: %d, reg: %04x, val: %04x",
           master->id, dev->mdio_bus->id, dev->prtad, dev->devad,
           prtad, devad, reg, val);

   mdio_master_lock(master);
   ret = scd_mdio_bus_request(dev->mdio_bus, SCD_MDIO_SET, clause,
                              prtad, devad, reg);
   if (!ret)
      ret = scd_mdio_bus_request(dev->mdio_bus, SCD_MDIO_WRITE, clause,
                                 prtad, devad, val);
   mdio_master_unlock(master);

   if (ret < 0)
      return ret;

   dev_dbg(get_scd_dev(master->ctx),
           "cdev_write_ret, master: %d, bus: %d, prtad: %d, devad: %d, "
           "reg: %04x, val: %04x",
           master->id, dev->mdio_bus->id, prtad, devad, reg, val);

   return sizeof(val);
}

static const struct file_operations scd_mdio_cdev_fops = {
   .owner   = THIS_MODULE,
   .open    = scd_mdio_cdev_open,
   .read    = scd_mdio_cdev_read,
   .write   = scd_mdio_cdev_write,
   .llseek  = noop_llseek,
};

/* Sysfs attributes for mdio devices */
static ssize_t mdio_id_show(struct device *dev, struct device_attribute *attr, char *buf)
{
   struct mdio_device *mdio_dev = to_mdio_device(dev);
   struct scd_mdio_bus *bus = (struct scd_mdio_bus*)mdio_dev->bus->priv;
   return sysfs_emit(buf, "mdio%d_%d_%d\n", bus->master->id, bus->id, mdio_dev->addr);
}
static DEVICE_ATTR_RO(mdio_id);

static struct attribute *scd_mdio_dev_attrs[] = {
   &dev_attr_mdio_id.attr,
   NULL,
};
ATTRIBUTE_GROUPS(scd_mdio_dev);

static struct device_type mdio_bus_gearbox_type = {
   .name = "scd-mdio",
   .groups = scd_mdio_dev_groups,
};

static int gearbox_ioctl(struct net_device *netdev, struct ifreq *req, int cmd)
{
   struct scd_mdio_device *mdio_dev = netdev_priv(netdev);

   return mdio_mii_ioctl(&mdio_dev->mdio_if, if_mii(req), cmd);
}

static const struct net_device_ops gearbox_netdev_ops = {
#if LINUX_VERSION_CODE < KERNEL_VERSION(5, 15, 0)
    // For backward compatibility with kernel versions before bookworm
   .ndo_do_ioctl = gearbox_ioctl,
#else
   .ndo_eth_ioctl = gearbox_ioctl,
#endif
};

static void gearbox_setup(struct net_device *dev)
{
   dev->netdev_ops = &gearbox_netdev_ops;
}

static int __scd_mdio_device_add(struct scd_mdio_bus *bus, u16 dev_id, u16 prtad,
                                 u16 devad, u16 clause)
{
   char name[IFNAMSIZ];
   struct net_device *net_dev;
   struct mdio_device *mdio_dev = NULL;
   struct scd_mdio_device *scd_mdio_dev;
   struct device *cdev_dev = NULL;
   int minor;
   int err;

   if (dev_id >= PHY_MAX_ADDR) {
      return -EINVAL;
   }

   scnprintf(name, sizeof(name), "mdio%d_%d_%d", bus->master->id, bus->id, dev_id);
   net_dev = alloc_netdev(sizeof(*scd_mdio_dev), name,
                          NET_NAME_UNKNOWN, gearbox_setup);
   if (!net_dev) {
      return -ENOMEM;
   }

   scd_mdio_dev = netdev_priv(net_dev);
   scd_mdio_dev->net_dev = net_dev;
   scd_mdio_dev->mdio_bus = bus;
   scd_mdio_dev->prtad = prtad;
   scd_mdio_dev->devad = devad;
   scd_mdio_dev->mode_support = clause;
   scd_mdio_dev->mdio_if.prtad = scd_mdio_mii_id(prtad, devad, clause);
   scd_mdio_dev->mdio_if.mode_support = clause;
   scd_mdio_dev->mdio_if.dev = net_dev;
   scd_mdio_dev->mdio_if.mdio_read = scd_mdio_read;
   scd_mdio_dev->mdio_if.mdio_write = scd_mdio_write;
   scd_mdio_dev->id = dev_id;
   bus->dev_id_to_addr[dev_id] = scd_mdio_dev->mdio_if.prtad;

   err = register_netdev(net_dev);
   if (err) {
      goto fail_register_netdev;
   }

   mdio_dev = mdio_device_create(bus->mii_bus, dev_id);
   if (IS_ERR(mdio_dev)) {
      err = PTR_ERR(mdio_dev);
      goto fail_create_mdio;
   }
   mdio_dev->dev.type = &mdio_bus_gearbox_type;
   err = mdio_device_register(mdio_dev);
   if (err) {
      goto fail_register_mdio;
   }
   scd_mdio_dev->mdio_dev = mdio_dev;

   /* Create char device for rtnl_lock-free access */
   minor = ida_alloc_max(&scd_mdio_ida, SCD_MDIO_CDEV_MAX_DEVICES - 1, GFP_KERNEL);
   if (minor < 0) {
      err = minor;
      goto fail_ida;
   }
   scd_mdio_dev->minor = minor;
   scd_mdio_dev->devno = MKDEV(MAJOR(scd_mdio_devt), minor);

   cdev_init(&scd_mdio_dev->cdev, &scd_mdio_cdev_fops);
   scd_mdio_dev->cdev.owner = THIS_MODULE;
   err = cdev_add(&scd_mdio_dev->cdev, scd_mdio_dev->devno, 1);
   if (err)
      goto fail_cdev;

   cdev_dev = device_create(scd_mdio_cdev_class, get_scd_dev(bus->master->ctx),
                            scd_mdio_dev->devno, NULL, "%s", name);
   if (IS_ERR(cdev_dev)) {
      err = PTR_ERR(cdev_dev);
      goto fail_device_create;
   }

   list_add_tail(&scd_mdio_dev->list, &bus->device_list);
   dev_dbg(get_scd_dev(bus->master->ctx),
           "mdio device %s prtad %d devad %d clause %d", name, prtad, devad, clause);

   return 0;

fail_device_create:
   cdev_del(&scd_mdio_dev->cdev);
fail_cdev:
   ida_free(&scd_mdio_ida, minor);
fail_ida:
   mdio_device_remove(scd_mdio_dev->mdio_dev);
fail_register_mdio:
   mdio_device_free(mdio_dev);
fail_create_mdio:
   unregister_netdev(net_dev);
fail_register_netdev:
   free_netdev(net_dev);

   return err;
}

static struct scd_mdio_bus *scd_find_mdio_bus(struct scd_context *ctx, u16 master_id,
                                              u16 bus_id)
{
   struct scd_mdio_master *master;
   struct scd_mdio_bus *bus;

   list_for_each_entry(master, &ctx->mdio_master_list, list) {
      if (master->id != master_id)
         continue;
      list_for_each_entry(bus, &master->bus_list, list) {
         if (bus->id == bus_id)
            return bus;
      }
   }

   return NULL;
}

int scd_mdio_device_add(struct scd_context *ctx, u16 master_id, u16 bus_id,
                        u16 dev_id, u16 prtad, u16 devad, u16 clause)
{
   struct scd_mdio_bus *bus;
   struct scd_mdio_device *device;

   bus = scd_find_mdio_bus(ctx, master_id, bus_id);
   if (!bus) {
      dev_warn(get_scd_dev(ctx), "failed to find mdio bus %u:%u\n", master_id,
               bus_id);
      return -EEXIST;
   }

   list_for_each_entry(device, &bus->device_list, list) {
      if (device->id == dev_id) {
         dev_warn(get_scd_dev(ctx), "existing mdio device %u on bus %u:%u\n",
                  dev_id, master_id, bus_id);
         return -EEXIST;
      }
   }

   return __scd_mdio_device_add(bus, dev_id, prtad, devad, clause);
}

static int scd_mdio_bus_add(struct scd_mdio_master *master, int id)
{
   struct scd_mdio_bus *scd_mdio_bus;
   struct mii_bus *mii_bus;
   int err = -ENODEV;

   scd_mdio_bus = kzalloc(sizeof(*scd_mdio_bus), GFP_KERNEL);
   if (!scd_mdio_bus) {
      return -ENOMEM;
   }

   scd_mdio_bus->master = master;
   scd_mdio_bus->id = id;
   INIT_LIST_HEAD(&scd_mdio_bus->device_list);

   mii_bus = mdiobus_alloc();
   if (!mii_bus) {
      kfree(scd_mdio_bus);
      return -ENOMEM;
   }
   mii_bus->read = scd_mii_bus_read;
   mii_bus->write = scd_mii_bus_write;
   mii_bus->name = "scd-mdio";
   mii_bus->priv = scd_mdio_bus;
   mii_bus->parent = get_scd_dev(master->ctx);
   mii_bus->phy_mask = GENMASK(31, 0);
   scnprintf(mii_bus->id, MII_BUS_ID_SIZE,
             "scd-%s-mdio-%02x:%02x", get_scd_name(master->ctx),
             master->id, id);

   err = mdiobus_register(mii_bus);
   if (err) {
      goto fail;
   }

   scd_mdio_bus->mii_bus = mii_bus;
   mdio_master_lock(master);
   list_add_tail(&scd_mdio_bus->list, &master->bus_list);
   mdio_master_unlock(master);

   return 0;

fail:
   mdiobus_free(scd_mdio_bus->mii_bus);
   kfree(scd_mdio_bus);
   return err;
}

static void scd_mdio_device_remove(struct scd_mdio_device *device)
{
   struct net_device *net_dev = device->net_dev;

   device_destroy(scd_mdio_cdev_class, device->devno);
   cdev_del(&device->cdev);
   ida_free(&scd_mdio_ida, device->minor);
   mdio_device_remove(device->mdio_dev);
   mdio_device_free(device->mdio_dev);
   unregister_netdev(net_dev);
   free_netdev(net_dev);
}

static void scd_mdio_master_remove(struct scd_mdio_master *master)
{
   struct scd_mdio_bus *bus;
   struct scd_mdio_bus *tmp_bus;
   struct scd_mdio_device *device;
   struct scd_mdio_device *tmp_device;

   mdio_master_reset(master);

   list_for_each_entry_safe(bus, tmp_bus, &master->bus_list, list) {
      list_for_each_entry_safe(device, tmp_device, &bus->device_list, list) {
         list_del(&device->list);
         scd_mdio_device_remove(device);
      }
      list_del(&bus->list);
      if (bus->mii_bus) {
         mdiobus_unregister(bus->mii_bus);
         mdiobus_free(bus->mii_bus);
      }
      kfree(bus);
   }
   list_del(&master->list);

   mutex_destroy(&master->mutex);
   kfree(master);
   scd_mdio_cdev_deinit();
}

void scd_mdio_remove_all(struct scd_context *ctx)
{
   struct scd_mdio_master *master;
   struct scd_mdio_master *tmp_master;

   list_for_each_entry_safe(master, tmp_master, &ctx->mdio_master_list, list) {
      scd_mdio_master_remove(master);
   }
}

int scd_mdio_master_add(struct scd_context *ctx, u32 addr, u16 id, u16 bus_count,
                        u16 speed)
{
   struct scd_mdio_master *master;
   int err = 0;
   int i;

   err = scd_mdio_cdev_init();
   if (err)
      return err;

   list_for_each_entry(master, &ctx->mdio_master_list, list) {
      if (master->id == id) {
         err = -EEXIST;
         goto fail_alloc;
      }
   }

   master = kzalloc(sizeof(*master), GFP_KERNEL);
   if (!master) {
      err = -ENOMEM;
      goto fail_alloc;
   }

   master->ctx = ctx;
   mutex_init(&master->mutex);
   master->id = id;
   master->req_lo = addr + MDIO_REQUEST_LO_OFFSET;
   master->req_hi = addr + MDIO_REQUEST_HI_OFFSET;
   master->cs = addr + MDIO_CONTROL_STATUS_OFFSET;
   master->resp = addr + MDIO_RESPONSE_OFFSET;
   master->speed = speed;
   INIT_LIST_HEAD(&master->bus_list);

   for (i = 0; i < bus_count; ++i) {
      err = scd_mdio_bus_add(master, i);
      if (err) {
         goto fail_bus;
      }
   }

   mdio_master_reset(master);

   list_add_tail(&master->list, &ctx->mdio_master_list);
   dev_dbg(get_scd_dev(ctx), "mdio master 0x%x:0x%x bus_count %d speed %d ",
           id, addr, bus_count, speed);

   return 0;

fail_bus:
   scd_mdio_master_remove(master);
   return err;

fail_alloc:
   scd_mdio_cdev_deinit();
   return err;
}

static int scd_mdio_cdev_init(void)
{
   int err = 0;

   mutex_lock(&scd_mdio_cdev_mutex);
   if (scd_mdio_cdev_refcount++ > 0)
      goto out;

   err = alloc_chrdev_region(&scd_mdio_devt, 0, SCD_MDIO_CDEV_MAX_DEVICES, "scd-mdio");
   if (err)
      goto fail;

#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 4, 0)
   scd_mdio_cdev_class = class_create("scd_mdio");
#else
   scd_mdio_cdev_class = class_create(THIS_MODULE, "scd_mdio");
#endif
   if (IS_ERR(scd_mdio_cdev_class)) {
      err = PTR_ERR(scd_mdio_cdev_class);
      unregister_chrdev_region(scd_mdio_devt, SCD_MDIO_CDEV_MAX_DEVICES);
      goto fail;
   }

out:
   mutex_unlock(&scd_mdio_cdev_mutex);
   return 0;

fail:
   scd_mdio_cdev_refcount--;
   mutex_unlock(&scd_mdio_cdev_mutex);
   return err;
}

static void scd_mdio_cdev_deinit(void)
{
   mutex_lock(&scd_mdio_cdev_mutex);
   if (--scd_mdio_cdev_refcount > 0) {
      mutex_unlock(&scd_mdio_cdev_mutex);
      return;
   }

   class_destroy(scd_mdio_cdev_class);
   unregister_chrdev_region(scd_mdio_devt, SCD_MDIO_CDEV_MAX_DEVICES);
   ida_destroy(&scd_mdio_ida);
   mutex_unlock(&scd_mdio_cdev_mutex);
}
