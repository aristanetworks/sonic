/* Copyright (c) 2017 Arista Networks, Inc.
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

#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/moduleparam.h>
#include <linux/sysfs.h>
#include <linux/version.h>
#include <linux/hwmon.h>
#include <linux/hwmon-sysfs.h>
#include <linux/delay.h>
#include <linux/leds.h>
#include <linux/gpio.h>
#include <linux/i2c.h>
#include <linux/pci.h>
#include <linux/stat.h>
#include <linux/mii.h>
#include <linux/netdevice.h>
#include <linux/phy.h>

#include "scd.h"
#include "scd-fan.h"
#include "scd-hwmon.h"
#include "scd-mdio.h"

// sizeof_field was introduced in v4.15 and FIELD_SIZEOF removed in 4.20
#ifndef sizeof_field
# define sizeof_field FIELD_SIZEOF
#endif

#define SCD_MODULE_NAME "scd-hwmon"

#define SMBUS_REQUEST_OFFSET 0x10
#define SMBUS_CONTROL_STATUS_OFFSET 0x20
#define SMBUS_RESPONSE_OFFSET 0x30

#define I2C_SMBUS_I2C_BLOCK_DATA_MSG 0x9

#define RESET_SET_OFFSET 0x00
#define RESET_CLEAR_OFFSET 0x10

#define MASTER_DEFAULT_BUS_COUNT 8
#define MASTER_DEFAULT_MAX_RETRIES 6

#define MAX_CONFIG_LINE_SIZE 100

#define SMBUS_BLOCK_READ_TIMEOUT_STEP 1

#define FAIL_REASON_MAX_SZ 50
#define SET_FAIL_REASON(fail_reason, ...) \
   snprintf(fail_reason, FAIL_REASON_MAX_SZ, ##__VA_ARGS__)

static int smbus_master_max_retries = MASTER_DEFAULT_MAX_RETRIES;
module_param(smbus_master_max_retries, int, S_IRUSR | S_IWUSR);
MODULE_PARM_DESC(smbus_master_max_retries,
                 "Number of smbus transaction retries to perform on error");

struct scd_context {
   struct pci_dev *pdev;
   size_t res_size;

   struct list_head list;

   struct mutex mutex;
   bool initialized;

   struct list_head gpio_list;
   struct list_head reset_list;
   struct list_head led_list;
   struct list_head smbus_master_list;
   struct list_head mdio_master_list;
   struct list_head xcvr_list;
   struct list_head fan_group_list;
};

struct scd_smbus_master {
   struct scd_context *ctx;
   struct list_head list;

   u32 id;
   u32 req;
   u32 cs;
   u32 resp;
   struct mutex mutex;
   struct list_head bus_list;
   bool br_supported;

   int max_retries;
};

struct bus_params {
   struct list_head list;
   u16 addr;
   u8 t;
   u8 datw;
   u8 datr;
   u8 ed;
};

const struct bus_params default_smbus_params = {
   .t = 1,
   .datw = 3,
   .datr = 3,
   .ed = 0,
};

struct scd_smbus {
   struct scd_smbus_master *master;
   struct list_head list;

   u32 id;
   struct list_head params;

   struct i2c_adapter adap;
};

#define LED_NAME_MAX_SZ 40
struct scd_led {
   struct scd_context *ctx;
   struct list_head list;

   u32 addr;
   char name[LED_NAME_MAX_SZ];
   struct led_classdev cdev;
};

struct scd_gpio_attribute {
   struct device_attribute dev_attr;
   struct scd_context *ctx;

   u32 addr;
   u32 bit;
   u32 active_low;
};

#define GPIO_NAME_MAX_SZ 32
struct scd_xcvr_attribute {
   struct device_attribute dev_attr;
   struct scd_xcvr *xcvr;

   char name[GPIO_NAME_MAX_SZ];
   u32 bit;
   u32 active_low;
   u32 clear_on_read;
   u32 clear_on_read_value;
};

struct scd_gpio {
   char name[GPIO_NAME_MAX_SZ];
   struct scd_gpio_attribute attr;
   struct list_head list;
};

#define XCVR_ATTR_MAX_COUNT 9
struct scd_xcvr {
   struct scd_context *ctx;
   struct scd_xcvr_attribute attr[XCVR_ATTR_MAX_COUNT];
   struct list_head list;

   char name[GPIO_NAME_MAX_SZ];
   u32 addr;
};

#define __ATTR_NAME_PTR(_name, _mode, _show, _store) {  \
   .attr = { .name = _name,                             \
             .mode = VERIFY_OCTAL_PERMISSIONS(_mode) }, \
   .show = _show,                                       \
   .store = _store                                      \
}

#define to_scd_gpio_attr(_dev_attr) \
   container_of(_dev_attr, struct scd_gpio_attribute, dev_attr)

#define to_scd_xcvr_attr(_dev_attr) \
   container_of(_dev_attr, struct scd_xcvr_attribute, dev_attr)

#define SCD_GPIO_ATTR(_name, _mode, _show, _store, _ctx, _addr, _bit, _active_low) \
   { .dev_attr = __ATTR_NAME_PTR(_name, _mode, _show, _store),                     \
     .ctx = _ctx,                                                                  \
     .addr = _addr,                                                                \
     .bit = _bit,                                                                  \
     .active_low = _active_low                                                     \
   }

#define SCD_RW_GPIO_ATTR(_name, _ctx, _addr, _bit, _active_low)                    \
   SCD_GPIO_ATTR(_name, S_IRUGO | S_IWUSR, attribute_gpio_get, attribute_gpio_set, \
                 _ctx, _addr, _bit, _active_low)

#define SCD_RO_GPIO_ATTR(_name, _ctx, _addr, _bit, _active_low) \
   SCD_GPIO_ATTR(_name, S_IRUGO, attribute_gpio_get, NULL,      \
                 _ctx, _addr, _bit, _active_low)

#define SCD_XCVR_ATTR(_xcvr_attr, _name, _name_size, _mode, _show, _store, _xcvr, \
                      _bit, _active_low, _clear_on_read)                          \
   do {                                                                           \
      snprintf(_xcvr_attr.name, _name_size, _name);                               \
      _xcvr_attr.dev_attr =                                                       \
         (struct device_attribute)__ATTR_NAME_PTR(_xcvr_attr.name, _mode, _show,  \
                                                  _store);                        \
      _xcvr_attr.xcvr = _xcvr;                                                    \
      _xcvr_attr.bit = _bit;                                                      \
      _xcvr_attr.active_low = _active_low;                                        \
      _xcvr_attr.clear_on_read = _clear_on_read;                                  \
   } while(0);

#define SCD_RW_XCVR_ATTR(_xcvr_attr, _name, _name_size, _xcvr, _bit,  \
                         _active_low, _clear_on_read)                 \
   SCD_XCVR_ATTR(_xcvr_attr, _name, _name_size, S_IRUGO | S_IWUSR,    \
                 attribute_xcvr_get, attribute_xcvr_set, _xcvr, _bit, \
                 _active_low, _clear_on_read)

#define SCD_RO_XCVR_ATTR(_xcvr_attr, _name, _name_size, _xcvr, _bit,         \
                         _active_low, _clear_on_read)                        \
   SCD_XCVR_ATTR(_xcvr_attr, _name, _name_size, S_IRUGO, attribute_xcvr_get, \
                 NULL, _xcvr, _bit, _active_low, _clear_on_read)

#define to_scd_fan_attr(_sensor_attr) \
   container_of(_sensor_attr, struct scd_fan_attribute, sensor_attr)

#define __SENSOR_ATTR_NAME_PTR(_name, _mode, _show, _store, _index)   \
   { .dev_attr = __ATTR_NAME_PTR(_name, _mode, _show, _store),        \
     .index = _index                                                  \
   }

#define SCD_FAN_ATTR(_attr, _fan, _name, _index, _suffix, _mode, _show, _store)  \
   do {                                                                          \
      snprintf(_attr.name, sizeof(_attr.name), "%s%zu%s", _name,                 \
               _index + 1, _suffix);                                             \
      _attr.sensor_attr = (struct sensor_device_attribute)                       \
         __SENSOR_ATTR_NAME_PTR(_attr.name, _mode, _show, _store, _index);       \
      _attr.fan = _fan;                                                          \
   } while(0)

struct scd_reset_attribute {
   struct device_attribute dev_attr;
   struct scd_context *ctx;

   u32 addr;
   u32 bit;
};

#define RESET_NAME_MAX_SZ 50
struct scd_reset {
   char name[RESET_NAME_MAX_SZ];
   struct scd_reset_attribute attr;
   struct list_head list;
};

#define to_scd_reset_attr(_dev_attr) \
   container_of(_dev_attr, struct scd_reset_attribute, dev_attr)

#define SCD_RESET_ATTR(_name, _ctx, _addr, _bit)                                \
   { .dev_attr = __ATTR_NAME_PTR(_name, S_IRUGO | S_IWUSR, attribute_reset_get, \
                                 attribute_reset_set),                          \
     .ctx = _ctx,                                                               \
     .addr = _addr,                                                             \
     .bit = _bit,                                                               \
   }

struct scd_fan;
struct scd_fan_group;

#define FAN_ATTR_NAME_MAX_SZ 16
struct scd_fan_attribute {
   struct sensor_device_attribute sensor_attr;
   struct scd_fan *fan;

   char name[FAN_ATTR_NAME_MAX_SZ];
};

/* Driver data for each fan slot */
struct scd_fan {
   struct scd_fan_group *fan_group;
   struct list_head list;

   u8 index;
   const struct fan_info *info;

   struct scd_fan_attribute *attrs;
   size_t attr_count;

   struct led_classdev led_cdev;
   char led_name[LED_NAME_MAX_SZ];
};

#define FAN_GROUP_NAME_MAX_SZ 50
/* Driver data for each fan group */
struct scd_fan_group {
   struct scd_context *ctx;
   struct list_head list;

   char name[FAN_GROUP_NAME_MAX_SZ];
   const struct fan_platform *platform;
   struct list_head slot_list;

   struct device *hwmon_dev;
   const struct attribute_group *groups[2];
   struct attribute_group group;

   size_t attr_count;
   size_t attr_index_count;

   u32 addr_base;
   size_t fan_count;
};

union smbus_request_reg {
   u32 reg;
   struct {
      u32 d:8;
      u32 ss:6;
      u32 ed:1;
      u32 br:1;
      u32 dat:2;
      u32 t:2;
      u32 sp:1;
      u32 da:1;
      u32 dod:1;
      u32 st:1;
      u32 bs:4;
      u32 ti:4;
   } __packed;
};

union smbus_ctrl_status_reg {
   u32 reg;
   struct {
      u32 fs:10;
      u32 reserved1:3;
      u32 foe:1;
      u32 reserved2:12;
      u32 brb:1;
      u32 reserved3:1;
      u32 ver:2;
      u32 fe:1;
      u32 reset:1;
   } __packed;
};

union smbus_response_reg {
   u32 reg;
   struct {
      u32 d:8;
      u32 bus_conflict_error:1;
      u32 timeout_error:1;
      u32 ack_error:1;
      u32 flushed:1;
      u32 ti:4;
      u32 ss:6;
      u32 reserved2:8;
      u32 foe:1;
      u32 fe:1;
   } __packed;
};

/* locking functions */
static struct mutex scd_hwmon_mutex;

static void module_lock(void)
{
   mutex_lock(&scd_hwmon_mutex);
}

static void module_unlock(void)
{
   mutex_unlock(&scd_hwmon_mutex);
}

static void smbus_master_lock(struct scd_smbus_master *master)
{
   mutex_lock(&master->mutex);
}

static void smbus_master_unlock(struct scd_smbus_master *master)
{
   mutex_unlock(&master->mutex);
}

static void mdio_master_lock(struct scd_mdio_master *master)
{
   mutex_lock(&master->mutex);
}

static void mdio_master_unlock(struct scd_mdio_master *master)
{
   mutex_unlock(&master->mutex);
}

static void scd_lock(struct scd_context *ctx)
{
   mutex_lock(&ctx->mutex);
}

static void scd_unlock(struct scd_context *ctx)
{
   mutex_unlock(&ctx->mutex);
}

/* SMBus functions */
static void smbus_master_write_req(struct scd_smbus_master *master,
                                   union smbus_request_reg req)
{
   u32 addr = (u32)master->req;
   scd_write_register(master->ctx->pdev, addr, req.reg);
}

static void smbus_master_write_cs(struct scd_smbus_master *master,
                                  union smbus_ctrl_status_reg cs)
{
   scd_write_register(master->ctx->pdev, master->cs, cs.reg);
}

static union smbus_ctrl_status_reg smbus_master_read_cs(struct scd_smbus_master *master)
{
   union smbus_ctrl_status_reg cs;
   cs.reg = scd_read_register(master->ctx->pdev, master->cs);
   return cs;
}

static union smbus_response_reg smbus_master_read_resp(struct scd_smbus_master *master)
{
   union smbus_ctrl_status_reg cs;
   union smbus_response_reg resp;
   u32 retries = 20;

   cs = smbus_master_read_cs(master);
   while (!cs.fs && --retries) {
      msleep(10);
      cs = smbus_master_read_cs(master);
   }
   if (!cs.fs)
      scd_dbg("smbus response: fifo still empty after retries");

   resp.reg = scd_read_register(master->ctx->pdev, master->resp);
   return resp;
}

static s32 smbus_check_resp(union smbus_response_reg resp, u32 tid,
                            char *fail_reason)
{
   const char *error;
   int error_ret = -EIO;

   if (resp.fe) {
      error = "fe";
      goto fail;
   }
   if (resp.ack_error) {
      error = "ack";
      goto fail;
   }
   if (resp.timeout_error) {
      error = "timeout";
      goto fail;
   }
   if (resp.bus_conflict_error) {
      error = "conflict";
      goto fail;
   }
   if (resp.flushed) {
      error = "flush";
      goto fail;
   }
   if (resp.ti != tid) {
      error = "tid";
      goto fail;
   }
   if (resp.foe) {
      error = "overflow";
      goto fail;
   }

   return 0;

fail:
   scd_dbg("smbus response: %s error. reg=0x%08x", error, resp.reg);
   if (fail_reason != NULL)
      SET_FAIL_REASON(fail_reason, "bad response: %s", error);
   return error_ret;
}

static u32 scd_smbus_func(struct i2c_adapter *adapter)
{
   return I2C_FUNC_SMBUS_QUICK | I2C_FUNC_SMBUS_BYTE |
      I2C_FUNC_SMBUS_BYTE_DATA | I2C_FUNC_SMBUS_WORD_DATA |
      I2C_FUNC_SMBUS_I2C_BLOCK | I2C_FUNC_SMBUS_BLOCK_DATA | I2C_FUNC_I2C;
}

static void smbus_master_reset(struct scd_smbus_master *master)
{
   union smbus_ctrl_status_reg cs;
   cs = smbus_master_read_cs(master);
   cs.reset = 1;
   cs.foe = 1;
   smbus_master_write_cs(master, cs);
   mdelay(50);
   cs.reset = 0;
   smbus_master_write_cs(master, cs);
   mdelay(50);
}

static const struct bus_params *get_smbus_params(struct scd_smbus *bus, u16 addr) {
   const struct bus_params *params = &default_smbus_params;
   struct bus_params *params_tmp;

   list_for_each_entry(params_tmp, &bus->params, list) {
      if (params_tmp->addr == addr) {
         params = params_tmp;
         break;
      }
   }

   return params;
}

static s32 scd_smbus_block_read(struct scd_smbus *bus, u16 addr, u8 command,
                                union i2c_smbus_data *data, int data_size)
{
   struct scd_smbus_master *master = bus->master;
   const struct bus_params *params;
   int i, t, ct;
   union smbus_request_reg req;
   union smbus_response_reg resp;
   union smbus_ctrl_status_reg cs;
   int ret = 0;
   u32 ss = 3;

   params = get_smbus_params(bus, addr);

   req.reg = 0;
   req.bs = bus->id;
   req.t = params->t;
   req.st = 1;
   req.ss = ss;
   req.d = (((addr & 0xff) << 1) | 0);
   req.dod = 1;
   for (i = 0; i < ss; ++i) {
      if (i == 1) {
         req.st = 0;
         req.ss = 0;
         req.d = command;
      }
      if (i == 2) {
         req.br = 1;
         req.st = 1;
         req.d = (((addr & 0xff) << 1) | 1);
      }
      req.da = ((!(req.dod || req.sp)) ? 1 : 0);
      smbus_master_write_req(master, req);
      req.ti++;
   }

   ++ss;
   if (params->t > 3) {
      t = 100;
   } else {
      t = (int[]){5, 35 + 5, 500 + 5, 1000 + 5}[params->t];
   }
   ct = 0;
   cs = smbus_master_read_cs(master);
   while (cs.brb && ct < t) {
      msleep(SMBUS_BLOCK_READ_TIMEOUT_STEP);
      ct += SMBUS_BLOCK_READ_TIMEOUT_STEP;
      cs = smbus_master_read_cs(master);
   }

   if (ct == t) {
      scd_warn("smbus response timeout(%d) cs=0x%x adapter=\"%s\"\n",
               t, cs.reg, bus->adap.name);
      return -EINVAL;
   }

   req.ti = 0;
   for (i = 0; i < ss; ++i) {
      resp = smbus_master_read_resp(master);
      ret = smbus_check_resp(resp, req.ti, NULL);
      if (ret)
         return ret;
      req.ti++;
      if (i == 3)
         ss += resp.d;

      if (i >= 3) {
         if (i - 3 >= data_size) {
            scd_warn("smbus read failed (output too big) addr=0x%02x " \
                     "reg=0x%02x data_size=0x%04x adapter=\"%s\"\n", addr,
                     command, data_size, bus->adap.name);
            return -EINVAL;
         }
         data->block[i - 3] = resp.d;
      }
   }

   return 0;
}

static s32 scd_smbus_do_impl(struct scd_smbus *bus, u16 addr, unsigned short flags,
                             char read_write, u8 command, int size,
                             union i2c_smbus_data *data, int data_size,
                             char *fail_reason)
{
   struct scd_smbus_master *master = bus->master;
   const struct bus_params *params;
   int i;
   union smbus_request_reg req;
   union smbus_response_reg resp;
   int ret = 0;
   u32 ss = 0;
   u32 data_offset = 0;
   char _fail_reason[FAIL_REASON_MAX_SZ] = {0};

   params = get_smbus_params(bus, addr);

   req.reg = 0;
   req.bs = bus->id;
   req.t = params->t;

   switch (size) {
   case I2C_SMBUS_QUICK:
      ss = 1;
      break;
   case I2C_SMBUS_BYTE:
      ss = 2;
      break;
   case I2C_SMBUS_BYTE_DATA:
      if (read_write == I2C_SMBUS_WRITE) {
         ss = 3;
      } else {
         ss = 4;
      }
      break;
   case I2C_SMBUS_WORD_DATA:
      if (read_write == I2C_SMBUS_WRITE) {
         ss = 4;
      } else {
         ss = 5;
      }
      break;
   case I2C_SMBUS_I2C_BLOCK_DATA_MSG:
      if (read_write == I2C_SMBUS_WRITE) {
         ss = 2 + data_size;
      } else {
         ss = 3 + data_size;
      }
      break;
   case I2C_SMBUS_I2C_BLOCK_DATA:
      data_offset = 1;
      if (read_write == I2C_SMBUS_WRITE) {
         ss = 2 + data->block[0];
      } else {
         ss = 3 + data->block[0];
      }
      break;
   case I2C_SMBUS_BLOCK_DATA:
      if (read_write == I2C_SMBUS_WRITE) {
         ss = 3 + data->block[0];
      } else {
         if (master->br_supported) {
            ret = scd_smbus_block_read(bus, addr, command, data, data_size);
            if (ret) {
               SET_FAIL_REASON(fail_reason, "block read failed");
               goto fail;
            }
            return 0;
         } else {
            ret = scd_smbus_do_impl(bus, addr, flags, I2C_SMBUS_READ, command,
                                    I2C_SMBUS_BYTE_DATA, data, data_size,
                                    _fail_reason);
            if (ret) {
               SET_FAIL_REASON(fail_reason, "block size: %s", _fail_reason);
               goto fail;
            }
         }
         ss = 4 + data->block[0];
      }
      break;
   }

   req.st = 1;
   req.ss = ss;
   req.d = (((addr & 0xff) << 1) | ((ss <= 2) ? read_write : 0));
   req.dod = 1;
   for (i = 0; i < ss; i++) {
      if (i == ss - 1) {
         req.sp = 1;
         req.ed = params->ed;
         if (read_write == I2C_SMBUS_WRITE) {
            req.dat = params->datw;
         } else {
            req.dat = params->datr;
         }
      }
      if (i == 1) {
         req.st = 0;
         req.ss = 0;
         req.d = command;
         if (ss == 2)
            req.dod = ((read_write == I2C_SMBUS_WRITE) ? 1 : 0);
         else
            req.dod = 1;
      }
      if ((i == 2 && read_write == I2C_SMBUS_READ)) {
         req.st = 1;
         req.d = (((addr & 0xff) << 1) | 1);
      }
      if (i >= 2 && (read_write == I2C_SMBUS_WRITE)) {
         req.d = data->block[data_offset + i - 2];
      }
      if ((i == 3 && read_write == I2C_SMBUS_READ)) {
         req.dod = 0;
      }
      req.da = ((!(req.dod || req.sp)) ? 1 : 0);
      smbus_master_write_req(master, req);
      req.ti++;
      req.st = 0;
   }

   req.ti = 0;
   for (i = 0; i < ss; i++) {
      resp = smbus_master_read_resp(master);
      ret = smbus_check_resp(resp, req.ti, fail_reason);
      if (ret) {
         goto fail;
      }
      req.ti++;
      if (read_write == I2C_SMBUS_READ) {
         if (size == I2C_SMBUS_BYTE || size == I2C_SMBUS_BYTE_DATA) {
            if (i == ss - 1) {
               data->byte = resp.d;
            }
         } else if (size == I2C_SMBUS_WORD_DATA) {
            if (i == ss - 2) {
               data->word = resp.d;
            } else if (i == ss - 1) {
               data->word |= (resp.d << 8);
            }
         } else {
            if (i >= 3) {
               if (size == I2C_SMBUS_I2C_BLOCK_DATA) {
                  if (i - 2 >= data_size) {
                     SET_FAIL_REASON(fail_reason, "buffer too short");
                     ret = -EINVAL;
                     goto fail;
                  }
                  data->block[i - 2] = resp.d;
               } else {
                  if (i - 3 >= data_size) {
                     SET_FAIL_REASON(fail_reason, "buffer too short");
                     ret = -EINVAL;
                     goto fail;
                  }
                  data->block[i - 3] = resp.d;
               }
            }
         }
      }
   }

   return 0;

fail:
   scd_dbg("smbus_do_impl %s failed addr=0x%02x reg=0x%02x size=0x%02x "
           "data_size=0x%x adapter=\"%s\" (%s)\n", (read_write) ? "read" : "write",
           addr, command, size, data_size, bus->adap.name, fail_reason);
   smbus_master_reset(master);
   return ret;
}

static s32 scd_smbus_do(struct scd_smbus *bus, u16 addr, unsigned short flags,
                        char read_write, u8 command, int size,
                        union i2c_smbus_data *data, int data_size,
                        char *fail_reason)
{
   struct scd_smbus_master *master = bus->master;
   s32 ret;

   smbus_master_lock(master);
   ret = scd_smbus_do_impl(bus, addr, flags, read_write, command, size, data,
                           data_size, fail_reason);
   smbus_master_unlock(master);

   return ret;
}

static s32 scd_smbus_access_impl(struct i2c_adapter *adap, u16 addr,
                                 unsigned short flags, char read_write,
                                 u8 command, int size, union i2c_smbus_data *data,
                                 int data_size)
{
   struct scd_smbus *bus = i2c_get_adapdata(adap);
   struct scd_smbus_master *master = bus->master;
   int retry = 0;
   int ret;
   char fail_reason[FAIL_REASON_MAX_SZ] = {0};

   scd_dbg("smbus %s do addr=0x%02x reg=0x%02x size=0x%02x data_size=0x%04x "
           "adapter=\"%s\"\n", (read_write) ? "read" : "write", addr, command,
           size, data_size, bus->adap.name);
   do {
      ret = scd_smbus_do(bus, addr, flags, read_write, command, size, data,
                         data_size, fail_reason);
      if (ret != -EIO)
         return ret;
      retry++;
      scd_dbg("smbus retrying... %d/%d", retry, master->max_retries);
   } while (retry < master->max_retries);

   scd_warn("smbus %s failed addr=0x%02x reg=0x%02x size=0x%02x data_size=0x%04x "
            "adapter=\"%s\" (%s)\n", (read_write) ? "read" : "write",
            addr, command, size, data_size, bus->adap.name, fail_reason);

   return -EIO;
}

static s32 scd_smbus_access(struct i2c_adapter *adap, u16 addr,
                            unsigned short flags, char read_write,
                            u8 command, int size, union i2c_smbus_data *data)
{
   return scd_smbus_access_impl(adap, addr, flags, read_write, command, size,
                                data, I2C_SMBUS_BLOCK_MAX + 2);
}

static int scd_smbus_master_xfer_get_command(struct i2c_msg *msg) {
   if ((msg->flags & I2C_M_RD) || (msg->len != 1)) {
      scd_dbg("i2c rw: unsupported command.\n");
      return -EINVAL;
   }
   return msg->buf[0];
}

static int scd_smbus_master_xfer(struct i2c_adapter *adap,
                           struct i2c_msg *msgs,
                           int num)
{
   struct scd_smbus *bus = i2c_get_adapdata(adap);
   int ret, command;
   int read_write;
   union i2c_smbus_data *data;
   int len;
   struct i2c_msg *msg;

   if (num > 2) {
      scd_err("i2c rw num=%d adapter=\"%s\" (unsupported request)\n",
              num, bus->adap.name);
      return -EINVAL;
   }

   if (num == 2) {
      command = scd_smbus_master_xfer_get_command(&msgs[0]);
      if (command < 0) {
         return command;
      }
      data = (union i2c_smbus_data*)msgs[1].buf;
      len = msgs[1].len;
      msg = &msgs[1];
   } else {
      command = msgs[0].buf[0];
      data = (union i2c_smbus_data*)&msgs[0].buf[1];
      len = msgs[0].len - 1;
      msg = &msgs[0];
   }

   scd_dbg("i2c rw num=%d adapter=\"%s\"\n", num, bus->adap.name);
   read_write = (msg->flags & I2C_M_RD) ? I2C_SMBUS_READ : 0;
   ret = scd_smbus_access_impl(adap, msg->addr, 0, read_write, command,
                               I2C_SMBUS_I2C_BLOCK_DATA_MSG, data, len);
   if (ret) {
      scd_warn("i2c rw error=0x%x adapter=\"%s\"\n", ret, bus->adap.name);
      return ret;
   }
   return num;
}

static struct i2c_algorithm scd_smbus_algorithm = {
   .master_xfer   = scd_smbus_master_xfer,
   .smbus_xfer    = scd_smbus_access,
   .functionality = scd_smbus_func,
};

static struct list_head scd_list;

static struct scd_context *get_context_for_pdev(struct pci_dev *pdev)
{
   struct scd_context *ctx;

   module_lock();
   list_for_each_entry(ctx, &scd_list, list) {
      if (ctx->pdev == pdev) {
         module_unlock();
         return ctx;
      }
   }
   module_unlock();

   return NULL;
}

static inline struct device *get_scd_dev(struct scd_context *ctx)
{
   return &ctx->pdev->dev;
}


static inline struct kobject *get_scd_kobj(struct scd_context *ctx)
{
   return &ctx->pdev->dev.kobj;
}

static struct scd_context *get_context_for_dev(struct device *dev)
{
   struct scd_context *ctx;

   module_lock();
   list_for_each_entry(ctx, &scd_list, list) {
      if (get_scd_dev(ctx) == dev) {
         module_unlock();
         return ctx;
      }
   }
   module_unlock();

   return NULL;
}

static int scd_smbus_bus_add(struct scd_smbus_master *master, int id)
{
   struct scd_smbus *bus;
   int err;

   bus = kzalloc(sizeof(*bus), GFP_KERNEL);
   if (!bus) {
      return -ENOMEM;
   }

   bus->master = master;
   bus->id = id;
   INIT_LIST_HEAD(&bus->params);
   bus->adap.owner = THIS_MODULE;
   bus->adap.class = 0;
   bus->adap.algo = &scd_smbus_algorithm;
   bus->adap.dev.parent = get_scd_dev(master->ctx);
   scnprintf(bus->adap.name,
             sizeof(bus->adap.name),
             "SCD %s SMBus master %d bus %d", pci_name(master->ctx->pdev),
             master->id, bus->id);
   i2c_set_adapdata(&bus->adap, bus);
   err = i2c_add_adapter(&bus->adap);
   if (err) {
      kfree(bus);
      return err;
   }

   smbus_master_lock(master);
   list_add_tail(&bus->list, &master->bus_list);
   smbus_master_unlock(master);

   return 0;
}

/*
 * Must be called with the scd lock held.
 */
static void scd_smbus_master_remove(struct scd_smbus_master *master)
{
   struct scd_smbus *bus;
   struct scd_smbus *tmp_bus;
   struct bus_params *params;
   struct bus_params *tmp_params;

   /* Remove all i2c_adapter first to make sure the scd_smbus and scd_smbus_master are
    * unused when removing them.
    */
   list_for_each_entry(bus, &master->bus_list, list) {
      i2c_del_adapter(&bus->adap);
   }

   smbus_master_reset(master);

   list_for_each_entry_safe(bus, tmp_bus, &master->bus_list, list) {
      list_for_each_entry_safe(params, tmp_params, &bus->params, list) {
         list_del(&params->list);
         kfree(params);
      }

      list_del(&bus->list);
      kfree(bus);
   }
   list_del(&master->list);

   mutex_destroy(&master->mutex);
   kfree(master);
}

/*
 * Must be called with the scd lock held.
 */
static void scd_smbus_remove_all(struct scd_context *ctx)
{
   struct scd_smbus_master *master;
   struct scd_smbus_master *tmp_master;

   list_for_each_entry_safe(master, tmp_master, &ctx->smbus_master_list, list) {
      scd_smbus_master_remove(master);
   }
}

static int scd_smbus_master_add(struct scd_context *ctx, u32 addr, u32 id,
                                u32 bus_count)
{
   struct scd_smbus_master *master;
   union smbus_ctrl_status_reg cs;
   int err = 0;
   int i;

   list_for_each_entry(master, &ctx->smbus_master_list, list) {
      if (master->id == id) {
         return -EEXIST;
      }
   }

   master = kzalloc(sizeof(*master), GFP_KERNEL);
   if (!master) {
      return -ENOMEM;
   }

   master->ctx = ctx;
   mutex_init(&master->mutex);
   master->id = id;
   master->req = addr + SMBUS_REQUEST_OFFSET;
   master->cs = addr + SMBUS_CONTROL_STATUS_OFFSET;
   master->resp = addr + SMBUS_RESPONSE_OFFSET;
   master->max_retries = smbus_master_max_retries;
   INIT_LIST_HEAD(&master->bus_list);

   for (i = 0; i < bus_count; ++i) {
      err = scd_smbus_bus_add(master, i);
      if (err) {
         goto fail_bus;
      }
   }

   smbus_master_reset(master);

   cs = smbus_master_read_cs(master);
   master->br_supported = (cs.ver >= 2);
   scd_dbg("smbus 0x%x:0x%x version %d", id, addr, cs.ver);

   list_add_tail(&master->list, &ctx->smbus_master_list);

   return 0;

fail_bus:
   scd_smbus_master_remove(master);
   return err;
}

/* MDIO bus functions */
static union mdio_ctrl_status_reg mdio_master_read_cs(struct scd_mdio_master *master)
{
   union mdio_ctrl_status_reg cs;

   cs.reg = scd_read_register(master->ctx->pdev, master->cs);
   return cs;
}

static void mdio_master_write_cs(struct scd_mdio_master *master,
                                 union mdio_ctrl_status_reg cs)
{
   scd_write_register(master->ctx->pdev, master->cs, cs.reg);
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
         scd_warn("mdio wait_resp failed on master %d", master->id);
         return -EOPNOTSUPP;
      }
   }

   scd_warn("mdio wait_resp timeout on master %d", master->id);

   return -EAGAIN;
}

u8 mdio_master_get_req_id(struct scd_mdio_master *master)
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
   scd_write_register(master->ctx->pdev, master->req_lo, req_lo.reg);

   req_hi.ri = mdio_master_get_req_id(master);
   scd_write_register(master->ctx->pdev, master->req_hi, req_hi.reg);

   err = mdio_master_wait_response(master);
   if (err)
      return err;

   mdio_master_reset_interrupt(master);

   resp.reg = scd_read_register(master->ctx->pdev, master->resp);
   if (resp.ts != 1 || resp.fe == 1) {
      scd_warn("mdio bus request failed in reading resp")
      return -EIO;
   }

   if (op == SCD_MDIO_READ)
      return resp.d;

   return 0;
}

static s32 scd_mii_bus_do(struct mii_bus *mii_bus, int addr, int op, int regnum, u16 val)
{
   struct scd_mdio_bus *mdio_bus = mii_bus->priv;
   int prtad = addr >> 5;
   int devad = addr & 0x1f;
   int clause = (addr & MDIO_PHY_ID_C45) ? 1 : 0;
   int err;

   scd_dbg("mii_bus_do, op: %d, master: %d, bus: %d, clause %d, prtad: %d, "
           "devad: %d, regnum: %04x, value: %04x", op, mdio_bus->master->id,
           mdio_bus->id, clause, prtad, devad, regnum, val);

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
   int dev_id = (prtad << 5) | devad;

   if (mode & MDIO_SUPPORTS_C45)
      dev_id |= MDIO_PHY_ID_C45;

   return dev_id;
}

static int scd_mdio_read(struct net_device *netdev, int prtad, int devad, u16 addr)
{
   struct scd_mdio_device *mdio_dev = netdev_priv(netdev);
   int dev_id = scd_mdio_mii_id(prtad, devad, mdio_dev->mode_support);

   scd_dbg("scd_mdio_read, dev_id: %04x, prtad: %d, devad: %d, addr: %04x", dev_id,
           prtad, devad, addr);
   return mdiobus_read(mdio_dev->mdio_bus->mii_bus, dev_id, addr);
}

static int scd_mdio_write(struct net_device *netdev, int prtad, int devad, u16 addr,
                          u16 value)
{
   struct scd_mdio_device *mdio_dev = netdev_priv(netdev);
   int dev_id = scd_mdio_mii_id(prtad, devad, mdio_dev->mode_support);

   scd_dbg("scd_mdio_write, dev_id: %04x, prtad: %d, devad: %d, addr: %04x, "
           "value: %04x", dev_id, prtad, devad, addr, value);
   return mdiobus_write(mdio_dev->mdio_bus->mii_bus, dev_id, addr, value);
}

static ssize_t mdio_id_show(struct device *dev, struct device_attribute *attr, char *buf)
{
   struct mdio_device *mdio_dev = to_mdio_device(dev);
   struct scd_mdio_bus *bus = (struct scd_mdio_bus*)mdio_dev->bus->priv;
   return sprintf(buf, "mdio%d_%d_%d\n", bus->master->id, bus->id, mdio_dev->addr);
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
   .ndo_do_ioctl = gearbox_ioctl,
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
   int err;

   scnprintf(name, sizeof(name), "mdio%d_%d_%d", bus->master->id, bus->id, dev_id);
   net_dev = alloc_netdev(sizeof(*scd_mdio_dev), name,
                          NET_NAME_UNKNOWN, gearbox_setup);
   if (!net_dev) {
      return -ENOMEM;
   }

   scd_mdio_dev = netdev_priv(net_dev);
   scd_mdio_dev->net_dev = net_dev;
   scd_mdio_dev->mdio_bus = bus;
   scd_mdio_dev->mode_support = clause;
   scd_mdio_dev->mdio_if.prtad = scd_mdio_mii_id(prtad, devad, clause);
   scd_mdio_dev->mdio_if.mode_support = clause;
   scd_mdio_dev->mdio_if.dev = net_dev;
   scd_mdio_dev->mdio_if.mdio_read = scd_mdio_read;
   scd_mdio_dev->mdio_if.mdio_write = scd_mdio_write;
   scd_mdio_dev->id = dev_id;

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

   list_add_tail(&scd_mdio_dev->list, &bus->device_list);
   scd_dbg("mdio device %s prtad %d devad %d clause %d", name, prtad, devad, clause);

   return 0;

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

static int scd_mdio_device_add(struct scd_context *ctx, u16 master_id, u16 bus_id,
                               u16 dev_id, u16 prtad, u16 devad, u16 clause)
{
   struct scd_mdio_bus *bus;
   struct scd_mdio_device *device;

   bus = scd_find_mdio_bus(ctx, master_id, bus_id);
   if (!bus) {
      scd_warn("failed to find mdio bus %u:%u\n", master_id, bus_id);
      return -EEXIST;
   }

   list_for_each_entry(device, &bus->device_list, list) {
      if (device->id == dev_id) {
         scd_warn("existing mdio device %u on bus %u:%u\n", dev_id, master_id,
                  bus_id);
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
             "scd-%s-mdio-%02x:%02x", pci_name(master->ctx->pdev),
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
}

static void scd_mdio_remove_all(struct scd_context *ctx)
{
   struct scd_mdio_master *master;
   struct scd_mdio_master *tmp_master;

   list_for_each_entry_safe(master, tmp_master, &ctx->mdio_master_list, list) {
      scd_mdio_master_remove(master);
   }
}

static int scd_mdio_master_add(struct scd_context *ctx, u32 addr, u16 id,
                               u16 bus_count, u16 speed)
{
   struct scd_mdio_master *master;
   int err = 0;
   int i;

   list_for_each_entry(master, &ctx->mdio_master_list, list) {
      if (master->id == id) {
         return -EEXIST;
      }
   }

   master = kzalloc(sizeof(*master), GFP_KERNEL);
   if (!master) {
      return -ENOMEM;
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
   scd_dbg("mdio master 0x%x:0x%x bus_count %d speed %d ", id, addr,
           bus_count, speed);

   return 0;

fail_bus:
   scd_mdio_master_remove(master);
   return err;
}

static void led_brightness_set(struct led_classdev *led_cdev,
                               enum led_brightness value)
{
   struct scd_led *led = container_of(led_cdev, struct scd_led, cdev);
   u32 reg;

   switch ((int)value) {
   case 0:
      reg = 0x0006ff00;
      break;
   case 1:
      reg = 0x1006ff00;
      break;
   case 2:
      reg = 0x0806ff00;
      break;
   case 3:
      reg = 0x1806ff00;
      break;
   case 4:
      reg = 0x1406ff00;
      break;
   case 5:
      reg = 0x0C06ff00;
      break;
   case 6:
      reg = 0x1C06ff00;
      break;
   default:
      reg = 0x1806ff00;
      break;
   }
   scd_write_register(led->ctx->pdev, led->addr, reg);
}

/*
 * Must be called with the scd lock held.
 */
static void scd_led_remove_all(struct scd_context *ctx)
{
   struct scd_led *led;
   struct scd_led *led_tmp;

   list_for_each_entry_safe(led, led_tmp, &ctx->led_list, list) {
      led_classdev_unregister(&led->cdev);
      list_del(&led->list);
      kfree(led);
   }
}

static struct scd_led *scd_led_find(struct scd_context *ctx, u32 addr)
{
   struct scd_led *led;

   list_for_each_entry(led, &ctx->led_list, list) {
      if (led->addr == addr)
         return led;
   }
   return NULL;
}

static int scd_led_add(struct scd_context *ctx, const char *name, u32 addr)
{
   struct scd_led *led;
   int ret;

   if (scd_led_find(ctx, addr))
      return -EEXIST;

   led = kzalloc(sizeof(*led), GFP_KERNEL);
   if (!led)
      return -ENOMEM;

   led->ctx = ctx;
   led->addr = addr;
   strncpy(led->name, name, sizeof_field(typeof(*led), name));
   INIT_LIST_HEAD(&led->list);

   led->cdev.name = led->name;
   led->cdev.brightness_set = led_brightness_set;

   ret = led_classdev_register(get_scd_dev(ctx), &led->cdev);
   if (ret) {
      kfree(led);
      return ret;
   }

   list_add_tail(&led->list, &ctx->led_list);

   return 0;
}

static ssize_t attribute_gpio_get(struct device *dev,
                                  struct device_attribute *devattr, char *buf)
{
   const struct scd_gpio_attribute *gpio = to_scd_gpio_attr(devattr);
   u32 reg = scd_read_register(gpio->ctx->pdev, gpio->addr);
   u32 res = !!(reg & (1 << gpio->bit));
   res = (gpio->active_low) ? !res : res;
   return sprintf(buf, "%u\n", res);
}

static ssize_t attribute_gpio_set(struct device *dev,
                                  struct device_attribute *devattr,
                                  const char *buf, size_t count)
{
   const struct scd_gpio_attribute *gpio = to_scd_gpio_attr(devattr);
   long value;
   int res;
   u32 reg;

   res = kstrtol(buf, 10, &value);
   if (res < 0)
      return res;

   if (value != 0 && value != 1)
      return -EINVAL;

   reg = scd_read_register(gpio->ctx->pdev, gpio->addr);
   if (gpio->active_low) {
      if (value)
         reg &= ~(1 << gpio->bit);
      else
         reg |= ~(1 << gpio->bit);
   } else {
      if (value)
         reg |= 1 << gpio->bit;
      else
         reg &= ~(1 << gpio->bit);
   }
   scd_write_register(gpio->ctx->pdev, gpio->addr, reg);

   return count;
}

static u32 scd_xcvr_read_register(const struct scd_xcvr_attribute *gpio)
{
   struct scd_xcvr *xcvr = gpio->xcvr;
   int i;
   u32 reg;

   reg = scd_read_register(gpio->xcvr->ctx->pdev, gpio->xcvr->addr);
   for (i = 0; i < XCVR_ATTR_MAX_COUNT; i++) {
      if (xcvr->attr[i].clear_on_read) {
         xcvr->attr[i].clear_on_read_value =
            xcvr->attr[i].clear_on_read_value | !!(reg & (1 << i));
      }
   }
   return reg;
}

static ssize_t attribute_xcvr_get(struct device *dev,
                                  struct device_attribute *devattr, char *buf)
{
   struct scd_xcvr_attribute *gpio = to_scd_xcvr_attr(devattr);
   u32 res;
   u32 reg;

   reg = scd_xcvr_read_register(gpio);
   res = !!(reg & (1 << gpio->bit));
   res = (gpio->active_low) ? !res : res;
   if (gpio->clear_on_read) {
      res = gpio->clear_on_read_value | res;
      gpio->clear_on_read_value = 0;
   }
   return sprintf(buf, "%u\n", res);
}

static ssize_t attribute_xcvr_set(struct device *dev,
                                  struct device_attribute *devattr,
                                  const char *buf, size_t count)
{
   const struct scd_xcvr_attribute *gpio = to_scd_xcvr_attr(devattr);
   long value;
   int res;
   u32 reg;

   res = kstrtol(buf, 10, &value);
   if (res < 0)
      return res;

   if (value != 0 && value != 1)
      return -EINVAL;

   reg = scd_xcvr_read_register(gpio);
   if (gpio->active_low) {
      if (value)
         reg &= ~(1 << gpio->bit);
      else
         reg |= ~(1 << gpio->bit);
   } else {
      if (value)
         reg |= 1 << gpio->bit;
      else
         reg &= ~(1 << gpio->bit);
   }
   scd_write_register(gpio->xcvr->ctx->pdev, gpio->xcvr->addr, reg);

   return count;
}

static void scd_gpio_unregister(struct scd_context *ctx, struct scd_gpio *gpio)
{
   sysfs_remove_file(get_scd_kobj(ctx), &gpio->attr.dev_attr.attr);
}

static void scd_xcvr_unregister(struct scd_context *ctx, struct scd_xcvr *xcvr)
{
   int i;

   for (i = 0; i < XCVR_ATTR_MAX_COUNT; i++) {
      if (xcvr->attr[i].xcvr) {
         sysfs_remove_file(get_scd_kobj(ctx), &xcvr->attr[i].dev_attr.attr);
      }
   }
}

static int scd_gpio_register(struct scd_context *ctx, struct scd_gpio *gpio)
{
   int res;

   res = sysfs_create_file(get_scd_kobj(ctx), &gpio->attr.dev_attr.attr);
   if (res) {
      pr_err("could not create %s attribute for gpio: %d",
             gpio->attr.dev_attr.attr.name, res);
      return res;
   }

   list_add_tail(&gpio->list, &ctx->gpio_list);
   return 0;
}

struct gpio_cfg {
   u32 bitpos;
   bool read_only;
   bool active_low;
   bool clear_on_read;
   const char *name;
};

static int scd_xcvr_register(struct scd_xcvr *xcvr, const struct gpio_cfg *cfgs,
                             size_t gpio_count)
{
   struct gpio_cfg gpio;
   int res;
   size_t i;
   size_t name_size;
   char name[GPIO_NAME_MAX_SZ];

   for (i = 0; i < gpio_count; i++) {
      gpio = cfgs[i];
      name_size = strlen(xcvr->name) + strlen(gpio.name) + 2;
      BUG_ON(name_size > GPIO_NAME_MAX_SZ);
      snprintf(name, name_size, "%s_%s", xcvr->name, gpio.name);
      if (gpio.read_only) {
         SCD_RO_XCVR_ATTR(xcvr->attr[gpio.bitpos], name, name_size, xcvr,
                          gpio.bitpos, gpio.active_low, gpio.clear_on_read);
      } else {
         SCD_RW_XCVR_ATTR(xcvr->attr[gpio.bitpos], name, name_size, xcvr,
                          gpio.bitpos, gpio.active_low, gpio.clear_on_read);
      }
      res = sysfs_create_file(get_scd_kobj(xcvr->ctx),
                              &xcvr->attr[gpio.bitpos].dev_attr.attr);
      if (res) {
         pr_err("could not create %s attribute for xcvr: %d",
                xcvr->attr[gpio.bitpos].dev_attr.attr.name, res);
         return res;
      }
   }

   return 0;
}

/*
 * Sysfs handlers for fans
 */

static ssize_t scd_fan_pwm_show(struct device *dev, struct device_attribute *da,
                                char *buf)
{
   struct sensor_device_attribute *attr = to_sensor_dev_attr(da);
   struct scd_fan_group *group = dev_get_drvdata(dev);
   u32 address = FAN_ADDR_3(group, speed, attr->index, pwm);
   u32 reg = scd_read_register(group->ctx->pdev, address);

   reg &= group->platform->mask_pwm;
   return sprintf(buf, "%u\n", reg);
}

static ssize_t scd_fan_pwm_store(struct device *dev, struct device_attribute *da,
                                 const char *buf, size_t count)
{
   struct sensor_device_attribute *attr = to_sensor_dev_attr(da);
   struct scd_fan_group *group = dev_get_drvdata(dev);
   u32 address = FAN_ADDR_3(group, speed, attr->index, pwm);
   u8 val;

   if (kstrtou8(buf, 0, &val))
      return -EINVAL;

   scd_write_register(group->ctx->pdev, address, val);
   return count;
}

static ssize_t scd_fan_present_show(struct device *dev,
                                    struct device_attribute *da,
                                    char *buf)
{
   struct sensor_device_attribute *attr = to_sensor_dev_attr(da);
   struct scd_fan_group *group = dev_get_drvdata(dev);
   struct scd_fan *fan = to_scd_fan_attr(attr)->fan;
   u32 address = FAN_ADDR(group, present);
   u32 reg = scd_read_register(group->ctx->pdev, address);

   return sprintf(buf, "%u\n", !!(reg & (1 << fan->index)));
}

static u32 scd_fan_id_read(struct scd_fan_group *fan_group, u32 index)
{
   u32 address = FAN_ADDR_2(fan_group, id, index);
   u32 reg = scd_read_register(fan_group->ctx->pdev, address);

   reg &= fan_group->platform->mask_id;
   return reg;
}

static ssize_t scd_fan_id_show(struct device *dev, struct device_attribute *da,
                               char *buf)
{
   struct sensor_device_attribute *attr = to_sensor_dev_attr(da);
   struct scd_fan_group *group = dev_get_drvdata(dev);
   struct scd_fan *fan = to_scd_fan_attr(attr)->fan;
   u32 reg = scd_fan_id_read(group, fan->index);

   return sprintf(buf, "%u\n", reg);
}

static ssize_t scd_fan_fault_show(struct device *dev, struct device_attribute *da,
                                  char *buf)
{
   struct sensor_device_attribute *attr = to_sensor_dev_attr(da);
   struct scd_fan_group *group = dev_get_drvdata(dev);
   struct scd_fan *fan = to_scd_fan_attr(attr)->fan;
   u32 address = FAN_ADDR(group, ok);
   u32 reg = scd_read_register(group->ctx->pdev, address);

   return sprintf(buf, "%u\n", !(reg & (1 << fan->index)));
}

static ssize_t scd_fan_input_show(struct device *dev, struct device_attribute *da,
                                  char *buf)
{
   struct sensor_device_attribute *attr = to_sensor_dev_attr(da);
   struct scd_fan_group *group = dev_get_drvdata(dev);
   struct scd_fan *fan = to_scd_fan_attr(attr)->fan;
   u32 address = FAN_ADDR_3(group, speed, attr->index, tach_outer);
   u32 reg = scd_read_register(group->ctx->pdev, address);
   u32 val = 0;

   reg &= group->platform->mask_tach;
   if (reg && fan->info->pulses)
      val = fan->info->hz * 60 / reg / fan->info->pulses;
   else
      return -EDOM;

   return sprintf(buf, "%u\n", val);
}

static u32 scd_fan_led_read(struct scd_fan *fan) {
   struct scd_fan_group *group = fan->fan_group;
   u32 addr_g = FAN_ADDR(group, green_led);
   u32 addr_r = FAN_ADDR(group, red_led);
   u32 reg_g = scd_read_register(group->ctx->pdev, addr_g);
   u32 reg_r = scd_read_register(group->ctx->pdev, addr_r);
   u32 val = 0;

   if ((reg_g & (1 << fan->index)) == 0)
      val += group->platform->mask_green_led;
   if ((reg_r & (1 << fan->index)) == 0)
      val += group->platform->mask_red_led;

   return val;
}

void scd_fan_led_write(struct scd_fan *fan, u32 val)
{
   struct scd_fan_group *group = fan->fan_group;
   u32 addr_g = FAN_ADDR(group, green_led);
   u32 addr_r = FAN_ADDR(group, red_led);
   u32 reg_g = scd_read_register(group->ctx->pdev, addr_g);
   u32 reg_r = scd_read_register(group->ctx->pdev, addr_r);

   if ((val & group->platform->mask_green_led) == 0)
      reg_g |= (1 << fan->index);
   else
      reg_g &= ~(1 << fan->index);

   if ((val & group->platform->mask_red_led) == 0)
      reg_r |= (1 << fan->index);
   else
      reg_r &= ~(1 << fan->index);

   scd_write_register(group->ctx->pdev, addr_g, reg_g);
   scd_write_register(group->ctx->pdev, addr_r, reg_r);
}

static ssize_t scd_fan_led_show(struct device *dev, struct device_attribute *da,
                                char *buf)
{
   struct sensor_device_attribute *attr = to_sensor_dev_attr(da);
   struct scd_fan *fan = to_scd_fan_attr(attr)->fan;
   u32 val = scd_fan_led_read(fan);

   return sprintf(buf, "%u\n", val);
}

static ssize_t scd_fan_led_store(struct device *dev, struct device_attribute *da,
                                 const char *buf, size_t count)
{
   struct sensor_device_attribute *attr = to_sensor_dev_attr(da);
   struct scd_fan *fan = to_scd_fan_attr(attr)->fan;
   u32 val;

   if (kstrtou32(buf, 0, &val))
      return -EINVAL;

   scd_fan_led_write(fan, val);
   return count;
}

static enum led_brightness fan_led_brightness_get(struct led_classdev *led_cdev)
{
   struct scd_fan *fan = container_of(led_cdev, struct scd_fan, led_cdev);

   return scd_fan_led_read(fan);
}

static void fan_led_brightness_set(struct led_classdev *led_cdev,
                                   enum led_brightness value)
{
   struct scd_fan *fan = container_of(led_cdev, struct scd_fan, led_cdev);

   scd_fan_led_write(fan, value);
}

static ssize_t scd_fan_airflow_show(struct device *dev,
                                    struct device_attribute *da,
                                    char *buf)
{
   struct sensor_device_attribute *attr = to_sensor_dev_attr(da);
   struct scd_fan *fan = to_scd_fan_attr(attr)->fan;

   return sprintf(buf, "%s\n", (fan->info->forward) ? "forward" : "reverse");
}

static ssize_t scd_fan_slot_show(struct device *dev,
                                 struct device_attribute *da,
                                 char *buf)
{
   struct sensor_device_attribute *attr = to_sensor_dev_attr(da);
   struct scd_fan *fan = to_scd_fan_attr(attr)->fan;

   return sprintf(buf, "%u\n", fan->index + 1);
}

/*
 * Must be called with the scd lock held.
 */
static void scd_gpio_remove_all(struct scd_context *ctx)
{
   struct scd_gpio *tmp_gpio;
   struct scd_gpio *gpio;

   list_for_each_entry_safe(gpio, tmp_gpio, &ctx->gpio_list, list) {
      scd_gpio_unregister(ctx, gpio);
      list_del(&gpio->list);
      kfree(gpio);
   }
}

static void scd_fan_group_unregister(struct scd_context *ctx,
                                     struct scd_fan_group *fan_group)
{
   struct scd_fan *tmp_fan;
   struct scd_fan *fan;

   if (fan_group->hwmon_dev) {
      hwmon_device_unregister(fan_group->hwmon_dev);
      fan_group->hwmon_dev = NULL;
      kfree(fan_group->group.attrs);
   }

   list_for_each_entry_safe(fan, tmp_fan, &fan_group->slot_list, list) {
      if (!IS_ERR_OR_NULL(fan->led_cdev.dev)) {
         led_classdev_unregister(&fan->led_cdev);
      }

      if (fan->attrs) {
         kfree(fan->attrs);
         fan->attrs = NULL;
      }

      list_del(&fan->list);
      kfree(fan);
   }
}

static void scd_fan_group_remove_all(struct scd_context *ctx)
{
   struct scd_fan_group *tmp_group;
   struct scd_fan_group *group;

   list_for_each_entry_safe(group, tmp_group, &ctx->fan_group_list, list) {
      scd_fan_group_unregister(ctx, group);
      list_del(&group->list);
      kfree(group);
   }
}

static int scd_fan_group_register(struct scd_context *ctx,
                                  struct scd_fan_group *fan_group)
{
   struct device *hwmon_dev;
   struct scd_fan *fan;
   size_t i;
   size_t attr = 0;
   int err;

   fan_group->group.attrs = kcalloc(fan_group->attr_count + 1,
                                    sizeof(*fan_group->group.attrs), GFP_KERNEL);
   if (!fan_group->group.attrs)
      return -ENOMEM;

   list_for_each_entry(fan, &fan_group->slot_list, list) {
      for (i = 0; i < fan->attr_count; ++i) {
         fan_group->group.attrs[attr++] = &fan->attrs[i].sensor_attr.dev_attr.attr;
      }
   }
   fan_group->groups[0] = &fan_group->group;

   hwmon_dev = hwmon_device_register_with_groups(get_scd_dev(ctx), fan_group->name,
                                                 fan_group, fan_group->groups);
   if (IS_ERR(hwmon_dev)) {
      kfree(fan_group->group.attrs);
      return PTR_ERR(hwmon_dev);
   }

   fan_group->hwmon_dev = hwmon_dev;

   list_for_each_entry(fan, &fan_group->slot_list, list) {
      fan->led_cdev.name = fan->led_name;
      fan->led_cdev.brightness_set = fan_led_brightness_set;
      fan->led_cdev.brightness_get = fan_led_brightness_get;
      err = led_classdev_register(get_scd_dev(ctx), &fan->led_cdev);
      if (err) {
         scd_warn("failed to create sysfs entry of led class for %s", fan->led_name);
      }
      scd_fan_led_write(fan, FAN_LED_COLOR_GREEN(fan));
   }

   return 0;
}

static void scd_xcvr_remove_all(struct scd_context *ctx)
{
   struct scd_xcvr *tmp_xcvr;
   struct scd_xcvr *xcvr;

   list_for_each_entry_safe(xcvr, tmp_xcvr, &ctx->xcvr_list, list) {
      scd_xcvr_unregister(ctx, xcvr);
      list_del(&xcvr->list);
      kfree(xcvr);
   }
}

static ssize_t attribute_reset_get(struct device *dev,
                                   struct device_attribute *devattr, char *buf)
{
   const struct scd_reset_attribute *reset = to_scd_reset_attr(devattr);
   u32 reg = scd_read_register(reset->ctx->pdev, reset->addr);
   u32 res = !!(reg & (1 << reset->bit));
   return sprintf(buf, "%u\n", res);
}

// write 1 -> set, 0 -> clear
static ssize_t attribute_reset_set(struct device *dev,
                                   struct device_attribute *devattr,
                                   const char *buf, size_t count)
{
   const struct scd_reset_attribute *reset = to_scd_reset_attr(devattr);
   u32 offset = RESET_SET_OFFSET;
   long value;
   int res;
   u32 reg;

   res = kstrtol(buf, 10, &value);
   if (res < 0)
      return res;

   if (value != 0 && value != 1)
      return -EINVAL;

   if (!value)
      offset = RESET_CLEAR_OFFSET;

   reg = 1 << reset->bit;
   scd_write_register(reset->ctx->pdev, reset->addr + offset, reg);

   return count;
}

static void scd_reset_unregister(struct scd_context *ctx, struct scd_reset *reset)
{
   sysfs_remove_file(get_scd_kobj(ctx), &reset->attr.dev_attr.attr);
}

static int scd_reset_register(struct scd_context *ctx, struct scd_reset *reset)
{
   int res;

   res = sysfs_create_file(get_scd_kobj(ctx), &reset->attr.dev_attr.attr);
   if (res) {
      pr_err("could not create %s attribute for reset: %d",
             reset->attr.dev_attr.attr.name, res);
      return res;
   }

   list_add_tail(&reset->list, &ctx->reset_list);
   return 0;
}

/*
 * Must be called with the scd lock held.
 */
static void scd_reset_remove_all(struct scd_context *ctx)
{
   struct scd_reset *tmp_reset;
   struct scd_reset *reset;

   list_for_each_entry_safe(reset, tmp_reset, &ctx->reset_list, list) {
      scd_reset_unregister(ctx, reset);
      list_del(&reset->list);
      kfree(reset);
   }
}

static int scd_xcvr_add(struct scd_context *ctx, const char *prefix,
                        const struct gpio_cfg *cfgs, size_t gpio_count,
                        u32 addr, u32 id)
{
   struct scd_xcvr *xcvr;
   int err;

   xcvr = kzalloc(sizeof(*xcvr), GFP_KERNEL);
   if (!xcvr) {
      err = -ENOMEM;
      goto fail;
   }

   err = snprintf(xcvr->name, sizeof_field(typeof(*xcvr), name),
                  "%s%u", prefix, id);
   if (err < 0) {
      goto fail;
   }

   xcvr->addr = addr;
   xcvr->ctx = ctx;

   err = scd_xcvr_register(xcvr, cfgs, gpio_count);
   if (err) {
      goto fail;
   }

   list_add_tail(&xcvr->list, &ctx->xcvr_list);
   return 0;

fail:
   if (xcvr)
      kfree(xcvr);

   return err;
}

static int scd_xcvr_sfp_add(struct scd_context *ctx, u32 addr, u32 id)
{
   static const struct gpio_cfg sfp_gpios[] = {
      {0, true,  false, false, "rxlos"},
      {1, true,  false, false, "txfault"},
      {2, true,  true,  false, "present"},
      {3, true,  false, true,  "rxlos_changed"},
      {4, true,  false, true,  "txfault_changed"},
      {5, true,  false, true,  "present_changed"},
      {6, false, false, false, "txdisable"},
      {7, false, false, false, "rate_select0"},
      {8, false, false, false, "rate_select1"},
   };

   scd_dbg("sfp %u @ 0x%04x\n", id, addr);
   return scd_xcvr_add(ctx, "sfp", sfp_gpios, ARRAY_SIZE(sfp_gpios), addr, id);
}

static int scd_xcvr_qsfp_add(struct scd_context *ctx, u32 addr, u32 id)
{
   static const struct gpio_cfg qsfp_gpios[] = {
      {0, true,  true,  false, "interrupt"},
      {2, true,  true,  false, "present"},
      {3, true,  false, true,  "interrupt_changed"},
      {5, true,  false, true,  "present_changed"},
      {6, false, false, false, "lp_mode"},
      {7, false, false, false, "reset"},
      {8, false, true,  false, "modsel"},
   };

   scd_dbg("qsfp %u @ 0x%04x\n", id, addr);
   return scd_xcvr_add(ctx, "qsfp", qsfp_gpios, ARRAY_SIZE(qsfp_gpios), addr, id);
}

static int scd_xcvr_osfp_add(struct scd_context *ctx, u32 addr, u32 id)
{
   static const struct gpio_cfg osfp_gpios[] = {
      {0, true,  true,  false, "interrupt"},
      {2, true,  true,  false, "present"},
      {3, true,  false, true,  "interrupt_changed"},
      {5, true,  false, true,  "present_changed"},
      {6, false, false, false, "lp_mode"},
      {7, false, false, false, "reset"},
      {8, false, true,  false, "modsel"},
   };

   scd_dbg("osfp %u @ 0x%04x\n", id, addr);
   return scd_xcvr_add(ctx, "osfp", osfp_gpios, ARRAY_SIZE(osfp_gpios), addr, id);
}

static int scd_gpio_add(struct scd_context *ctx, const char *name,
                        u32 addr, u32 bitpos, bool read_only, bool active_low)
{
   int err;
   struct scd_gpio *gpio;

   gpio = kzalloc(sizeof(*gpio), GFP_KERNEL);
   if (!gpio) {
      return -ENOMEM;
   }

   snprintf(gpio->name, sizeof_field(typeof(*gpio), name), name);
   if (read_only)
      gpio->attr = (struct scd_gpio_attribute)SCD_RO_GPIO_ATTR(
                           gpio->name, ctx, addr, bitpos, active_low);
   else
      gpio->attr = (struct scd_gpio_attribute)SCD_RW_GPIO_ATTR(
                           gpio->name, ctx, addr, bitpos, active_low);

   err = scd_gpio_register(ctx, gpio);
   if (err) {
      kfree(gpio);
      return err;
   }

   return 0;
}

static int scd_reset_add(struct scd_context *ctx, const char *name,
                         u32 addr, u32 bitpos)
{
   int err;
   struct scd_reset *reset;

   reset = kzalloc(sizeof(*reset), GFP_KERNEL);
   if (!reset) {
      return -ENOMEM;
   }

   snprintf(reset->name, sizeof_field(typeof(*reset), name), name);
   reset->attr = (struct scd_reset_attribute)SCD_RESET_ATTR(
                                                reset->name, ctx, addr, bitpos);

   err = scd_reset_register(ctx, reset);
   if (err) {
      kfree(reset);
      return err;
   }
   return 0;
}

#define SCD_FAN_ATTR_COUNT 8
static void scd_fan_add_attrs(struct scd_fan *fan, size_t index) {
   struct scd_fan_attribute *attrs = fan->attrs;

   SCD_FAN_ATTR(attrs[fan->attr_count], fan, "pwm", index, "" ,
                S_IRUGO|S_IWGRP|S_IWUSR, scd_fan_pwm_show, scd_fan_pwm_store);
   fan->attr_count++;
   SCD_FAN_ATTR(attrs[fan->attr_count], fan, "fan", index, "_id",
                S_IRUGO, scd_fan_id_show, NULL);
   fan->attr_count++;
   SCD_FAN_ATTR(attrs[fan->attr_count], fan, "fan", index, "_input",
                S_IRUGO, scd_fan_input_show, NULL);
   fan->attr_count++;
   SCD_FAN_ATTR(attrs[fan->attr_count], fan, "fan", index, "_fault",
                S_IRUGO, scd_fan_fault_show, NULL);
   fan->attr_count++;
   SCD_FAN_ATTR(attrs[fan->attr_count], fan, "fan", index, "_present",
                S_IRUGO, scd_fan_present_show, NULL);
   fan->attr_count++;
   SCD_FAN_ATTR(attrs[fan->attr_count], fan, "fan", index, "_led" ,
                S_IRUGO|S_IWGRP|S_IWUSR, scd_fan_led_show, scd_fan_led_store);
   fan->attr_count++;
   SCD_FAN_ATTR(attrs[fan->attr_count], fan, "fan", index, "_airflow",
                S_IRUGO, scd_fan_airflow_show, NULL);
   fan->attr_count++;
   SCD_FAN_ATTR(attrs[fan->attr_count], fan, "fan", index, "_slot",
                S_IRUGO, scd_fan_slot_show, NULL);
   fan->attr_count++;
}

static int scd_fan_add(struct scd_fan_group *fan_group, u32 index) {
   struct scd_fan *fan;
   const struct fan_info *fan_info;
   size_t i;
   u32 fan_id = scd_fan_id_read(fan_group, index);

   fan_info = fan_info_find(fan_group->platform->fan_infos,
                            fan_group->platform->fan_info_count, fan_id);
   if (!fan_info) {
      scd_err("no infomation for fan%u with id=%u", index + 1, fan_id)
      return -EINVAL;
   } else if (!fan_info->present) {
      scd_warn("fan%u with id=%u is not present", index + 1, fan_id)
   }

   fan = kzalloc(sizeof(*fan), GFP_KERNEL);
   if (!fan)
      return -ENOMEM;

   fan->fan_group = fan_group;
   fan->index = index;
   fan->info = fan_info;
   scnprintf(fan->led_name, LED_NAME_MAX_SZ, "fan%d", fan->index + 1);

   fan->attrs = kcalloc(SCD_FAN_ATTR_COUNT * fan_info->fans,
                        sizeof(*fan->attrs), GFP_KERNEL);
   if (!fan->attrs) {
      kfree(fan);
      return -ENOMEM;
   }

   for (i = 0; i < fan->info->fans; ++i) {
      scd_fan_add_attrs(fan, fan_group->attr_index_count++);
      if (fan_group->attr_index_count >= fan_group->platform->max_attr_count) {
         break;
      }
   }
   fan_group->attr_count += fan->attr_count;

   list_add_tail(&fan->list, &fan_group->slot_list);

   return 0;
}

static int scd_fan_group_add(struct scd_context *ctx, u32 addr, u32 platform_id,
                             u32 fan_count)
{
   struct scd_fan_group *fan_group;
   const struct fan_platform *platform;
   size_t i;
   int err;
   u32 reg;

   platform = fan_platform_find(platform_id);
   if (!platform) {
      scd_warn("no known fan group for platform id=%u", platform_id);
      return -EINVAL;
   }

   if (fan_count > platform->max_fan_count) {
      scd_warn("the fan num argument is larger than %zu", platform->max_fan_count);
      return -EINVAL;
   }

   reg = scd_read_register(ctx->pdev, addr + platform->platform_offset);
   if ((reg & platform->mask_platform) != platform_id) {
      scd_warn("fan group for platform id=%u does not match hardware", platform_id);
      return -EINVAL;
   }

   fan_group = kzalloc(sizeof(*fan_group), GFP_KERNEL);
   if (!fan_group) {
      return -ENOMEM;
   }

   scnprintf(fan_group->name, sizeof_field(typeof(*fan_group), name),
             "scd_fan_p%u", platform_id);
   fan_group->ctx = ctx;
   fan_group->addr_base = addr;
   fan_group->fan_count = fan_count;
   fan_group->platform = platform;
   INIT_LIST_HEAD(&fan_group->slot_list);

   for (i = 0; i < fan_count; ++i) {
      err = scd_fan_add(fan_group, i);
      if (err)
         goto fail;
   }

   err = scd_fan_group_register(ctx, fan_group);
   if (err)
      goto fail;

   list_add_tail(&fan_group->list, &ctx->fan_group_list);

   return 0;

fail:
   scd_fan_group_unregister(ctx, fan_group);
   kfree(fan_group);
   return err;
}

#define PARSE_INT_OR_RETURN(Buf, Tmp, Type, Ptr)        \
   do {                                                 \
      int ___ret = 0;                                   \
      Tmp = strsep(Buf, " ");                           \
      if (!Tmp || !*Tmp) {                              \
         return -EINVAL;                                \
      }                                                 \
      ___ret = kstrto##Type(Tmp, 0, Ptr);               \
      if (___ret) {                                     \
         return ___ret;                                 \
      }                                                 \
   } while(0)

#define PARSE_ADDR_OR_RETURN(Buf, Tmp, Type, Ptr, Size) \
   do {                                                 \
      PARSE_INT_OR_RETURN(Buf, Tmp, Type, Ptr);         \
      if (*(Ptr) > (Size)) {                            \
         return -EINVAL;                                \
      }                                                 \
   } while(0)

#define PARSE_STR_OR_RETURN(Buf, Tmp, Ptr)              \
   do {                                                 \
      Tmp = strsep(Buf, " ");                           \
      if (!Tmp || !*Tmp) {                              \
         return -EINVAL;                                \
      }                                                 \
      Ptr = Tmp;                                        \
   } while(0)

#define PARSE_END_OR_RETURN(Buf, Tmp)                   \
   do {                                                 \
      Tmp = strsep(Buf, " ");                           \
      if (Tmp) {                                        \
         return -EINVAL;                                \
      }                                                 \
   } while(0)


// new_smbus_master <addr> <accel_id> <bus_count:8>
static ssize_t parse_new_object_smbus_master(struct scd_context *ctx,
                                             char *buf, size_t count)
{
   u32 id;
   u32 addr;
   u32 bus_count = MASTER_DEFAULT_BUS_COUNT;

   const char *tmp;
   int res;

   if (!buf)
      return -EINVAL;

   PARSE_ADDR_OR_RETURN(&buf, tmp, u32, &addr, ctx->res_size);
   PARSE_INT_OR_RETURN(&buf, tmp, u32, &id);

   tmp = strsep(&buf, " ");
   if (tmp && *tmp) {
      res = kstrtou32(tmp, 0, &bus_count);
      if (res)
         return res;
      PARSE_END_OR_RETURN(&buf, tmp);
   }

   res = scd_smbus_master_add(ctx, addr, id, bus_count);
   if (res)
      return res;

   return count;
}

// new_mdio_device <master> <bus> <id> <portAddr> <devAddr> <clause>
static ssize_t parse_new_object_mdio_device(struct scd_context *ctx,
                                            char *buf, size_t count)
{
   u16 master;
   u16 bus;
   u16 id;
   u16 prtad;
   u16 devad;
   u16 clause;
   const char *tmp;
   int res;

   if (!buf)
      return -EINVAL;

   PARSE_INT_OR_RETURN(&buf, tmp, u16, &master);
   PARSE_INT_OR_RETURN(&buf, tmp, u16, &bus);
   PARSE_INT_OR_RETURN(&buf, tmp, u16, &id);
   PARSE_INT_OR_RETURN(&buf, tmp, u16, &prtad);
   PARSE_INT_OR_RETURN(&buf, tmp, u16, &devad);
   PARSE_INT_OR_RETURN(&buf, tmp, u16, &clause);
   PARSE_END_OR_RETURN(&buf, tmp);

   res = scd_mdio_device_add(ctx, master, bus, id, prtad, devad, clause);
   if (res)
      return res;

   return count;
}

// new_mdio_master <addr> <id> <bus_count> <speed>
static ssize_t parse_new_object_mdio_master(struct scd_context *ctx,
                                            char *buf, size_t count)
{
   u32 addr;
   u16 id;
   u16 bus_count;
   u16 bus_speed;
   const char *tmp;
   int res;

   if (!buf)
      return -EINVAL;

   PARSE_ADDR_OR_RETURN(&buf, tmp, u32, &addr, ctx->res_size);
   PARSE_INT_OR_RETURN(&buf, tmp, u16, &id);
   PARSE_INT_OR_RETURN(&buf, tmp, u16, &bus_count);
   PARSE_INT_OR_RETURN(&buf, tmp, u16, &bus_speed);
   PARSE_END_OR_RETURN(&buf, tmp);

   res = scd_mdio_master_add(ctx, addr, id, bus_count, bus_speed);
   if (res)
      return res;

   return count;
}

// new_led <addr> <name>
static ssize_t parse_new_object_led(struct scd_context *ctx,
                                    char *buf, size_t count)
{
   u32 addr;
   const char *name;

   const char *tmp;
   int res;

   if (!buf)
      return -EINVAL;

   PARSE_ADDR_OR_RETURN(&buf, tmp, u32, &addr, ctx->res_size);
   PARSE_STR_OR_RETURN(&buf, tmp, name);
   PARSE_END_OR_RETURN(&buf, tmp);

   res = scd_led_add(ctx, name, addr);
   if (res)
      return res;

   return count;
}

enum xcvr_type {
   XCVR_TYPE_SFP,
   XCVR_TYPE_QSFP,
   XCVR_TYPE_OSFP,
};

static ssize_t parse_new_object_xcvr(struct scd_context *ctx, enum xcvr_type type,
                                     char *buf, size_t count)
{
   u32 addr;
   u32 id;

   const char *tmp;
   int res;

   if (!buf)
      return -EINVAL;

   PARSE_ADDR_OR_RETURN(&buf, tmp, u32, &addr, ctx->res_size);
   PARSE_INT_OR_RETURN(&buf, tmp, u32, &id);
   PARSE_END_OR_RETURN(&buf, tmp);

   if (type == XCVR_TYPE_SFP)
      res = scd_xcvr_sfp_add(ctx, addr, id);
   else if (type == XCVR_TYPE_QSFP)
      res = scd_xcvr_qsfp_add(ctx, addr, id);
   else if (type == XCVR_TYPE_OSFP)
      res = scd_xcvr_osfp_add(ctx, addr, id);
   else
      res = -EINVAL;

   if (res)
      return res;

   return count;
}

// new_osfp <addr> <id>
static ssize_t parse_new_object_osfp(struct scd_context *ctx,
                                     char *buf, size_t count)
{
   return parse_new_object_xcvr(ctx, XCVR_TYPE_OSFP, buf, count);
}

// new_qsfp <addr> <id>
static ssize_t parse_new_object_qsfp(struct scd_context *ctx,
                                     char *buf, size_t count)
{
   return parse_new_object_xcvr(ctx, XCVR_TYPE_QSFP, buf, count);
}

// new_sfp <addr> <id>
static ssize_t parse_new_object_sfp(struct scd_context *ctx,
                                     char *buf, size_t count)
{
   return parse_new_object_xcvr(ctx, XCVR_TYPE_SFP, buf, count);
}

// new_reset <addr> <name> <bitpos>
static ssize_t parse_new_object_reset(struct scd_context *ctx,
                                      char *buf, size_t count)
{
   u32 addr;
   const char *name;
   u32 bitpos;

   const char *tmp;
   int res;

   if (!buf)
      return -EINVAL;

   PARSE_ADDR_OR_RETURN(&buf, tmp, u32, &addr, ctx->res_size);
   PARSE_STR_OR_RETURN(&buf, tmp, name);
   PARSE_INT_OR_RETURN(&buf, tmp, u32, &bitpos);
   PARSE_END_OR_RETURN(&buf, tmp);

   res = scd_reset_add(ctx, name, addr, bitpos);
   if (res)
      return res;

   return count;
}

// new_fan_group <addr> <platform> <fan_count>
static ssize_t parse_new_object_fan_group(struct scd_context *ctx,
                                          char *buf, size_t count)
{
   const char *tmp;
   u32 addr;
   u32 platform_id;
   u32 fan_count;
   int res;

   if (!buf)
      return -EINVAL;

   PARSE_ADDR_OR_RETURN(&buf, tmp, u32, &addr, ctx->res_size);
   PARSE_INT_OR_RETURN(&buf, tmp, u32, &platform_id);
   PARSE_INT_OR_RETURN(&buf, tmp, u32, &fan_count);
   PARSE_END_OR_RETURN(&buf, tmp);

   res = scd_fan_group_add(ctx, addr, platform_id, fan_count);
   if (res)
      return res;

   return count;
}

// new_gpio <addr> <name> <bitpos> <ro> <activeLow>
static ssize_t parse_new_object_gpio(struct scd_context *ctx,
                                     char *buf, size_t count)
{
   u32 addr;
   const char *name;
   u32 bitpos;
   u32 read_only;
   u32 active_low;

   const char *tmp;
   int res;

   if (!buf)
      return -EINVAL;

   PARSE_ADDR_OR_RETURN(&buf, tmp, u32, &addr, ctx->res_size);
   PARSE_STR_OR_RETURN(&buf, tmp, name);
   PARSE_INT_OR_RETURN(&buf, tmp, u32, &bitpos);
   PARSE_INT_OR_RETURN(&buf, tmp, u32, &read_only);
   PARSE_INT_OR_RETURN(&buf, tmp, u32, &active_low);
   PARSE_END_OR_RETURN(&buf, tmp);

   res = scd_gpio_add(ctx, name, addr, bitpos, read_only, active_low);
   if (res)
      return res;

   return count;
}

typedef ssize_t (*new_object_parse_func)(struct scd_context*, char*, size_t);
static struct {
   const char *name;
   new_object_parse_func func;
} funcs[] = {
   { "fan_group",       parse_new_object_fan_group},
   { "gpio",            parse_new_object_gpio },
   { "led",             parse_new_object_led },
   { "mdio_device",     parse_new_object_mdio_device },
   { "mdio_master",     parse_new_object_mdio_master },
   { "osfp",            parse_new_object_osfp },
   { "qsfp",            parse_new_object_qsfp },
   { "reset",           parse_new_object_reset },
   { "sfp",             parse_new_object_sfp },
   { "smbus_master",    parse_new_object_smbus_master },
   { NULL, NULL }
};

static ssize_t parse_new_object(struct scd_context *ctx, const char *buf,
                                size_t count)
{
   char tmp[MAX_CONFIG_LINE_SIZE];
   char *ptr = tmp;
   char *tok;
   int i = 0;
   ssize_t err;

   if (count >= MAX_CONFIG_LINE_SIZE) {
      scd_warn("new_object line is too long\n");
      return -EINVAL;
   }

   strncpy(tmp, buf, count);
   tmp[count] = 0;
   tok = strsep(&ptr, " ");
   if (!tok)
      return -EINVAL;

   while (funcs[i].name) {
      if (!strcmp(tok, funcs[i].name))
         break;
      i++;
   }

   if (!funcs[i].name)
      return -EINVAL;

   err = funcs[i].func(ctx, ptr, count - (ptr - tmp));
   if (err < 0)
      return err;

   return count;
}

typedef ssize_t (*line_parser_func)(struct scd_context *ctx, const char *buf,
   size_t count);

static ssize_t parse_lines(struct scd_context *ctx, const char *buf,
                           size_t count, line_parser_func parser)
{
   ssize_t res;
   size_t left = count;
   const char *nl;

   if (count == 0)
      return 0;

   while (true) {
      nl = strnchr(buf, left, '\n');
      if (!nl)
         nl = buf + left; // points on the \0

      res = parser(ctx, buf, nl - buf);
      if (res < 0)
         return res;
      left -= res;

      buf = nl;
      while (left && *buf == '\n') {
         buf++;
         left--;
      }
      if (!left)
         break;
   }

   return count;
}

static ssize_t new_object(struct device *dev, struct device_attribute *attr,
                          const char *buf, size_t count)
{
   ssize_t res;
   struct scd_context *ctx = get_context_for_dev(dev);

   if (!ctx) {
      return -ENODEV;
   }

   scd_lock(ctx);
   if (ctx->initialized) {
      scd_unlock(ctx);
      return -EBUSY;
   }
   res = parse_lines(ctx, buf, count, parse_new_object);
   scd_unlock(ctx);
   return res;
}

static DEVICE_ATTR(new_object, S_IWUSR|S_IWGRP, 0, new_object);

static struct scd_smbus *scd_find_smbus(struct scd_context *ctx, u16 bus_nr)
{
   struct scd_smbus_master *master;
   struct scd_smbus *bus;

   list_for_each_entry(master, &ctx->smbus_master_list, list) {
      list_for_each_entry(bus, &master->bus_list, list) {
         if (bus->adap.nr != bus_nr)
            continue;
         return bus;
      }
   }

   return NULL;
}

static ssize_t scd_set_smbus_params(struct scd_context *ctx, u16 bus,
                                    struct bus_params *params)
{
   struct bus_params *p;
   struct scd_smbus *scd_smbus = scd_find_smbus(ctx, bus);

   if (!scd_smbus) {
      scd_err("Cannot find bus %d to add tweak\n", bus);
      return -EINVAL;
   }

   list_for_each_entry(p, &scd_smbus->params, list) {
      if (p->addr == params->addr) {
         p->t = params->t;
         p->datw = params->datw;
         p->datr = params->datr;
         p->ed = params->ed;
         return 0;
      }
   }

   p = kzalloc(sizeof(*p), GFP_KERNEL);
   if (!p) {
      return -ENOMEM;
   }

   p->addr = params->addr;
   p->t = params->t;
   p->datw = params->datw;
   p->datr = params->datr;
   p->ed = params->ed;
   list_add_tail(&p->list, &scd_smbus->params);
   return 0;
}

static ssize_t parse_smbus_tweak(struct scd_context *ctx, const char *buf,
                                 size_t count)
{
   char buf_copy[MAX_CONFIG_LINE_SIZE];
   struct bus_params params;
   ssize_t err;
   char *ptr = buf_copy;
   const char *tmp;
   u16 bus;

   if (count >= MAX_CONFIG_LINE_SIZE) {
      scd_warn("smbus_tweak line is too long\n");
      return -EINVAL;
   }

   strncpy(buf_copy, buf, count);
   buf_copy[count] = 0;

   PARSE_INT_OR_RETURN(&ptr, tmp, u16, &bus);
   PARSE_INT_OR_RETURN(&ptr, tmp, u16, &params.addr);
   PARSE_INT_OR_RETURN(&ptr, tmp, u8, &params.t);
   PARSE_INT_OR_RETURN(&ptr, tmp, u8, &params.datr);
   PARSE_INT_OR_RETURN(&ptr, tmp, u8, &params.datw);
   PARSE_INT_OR_RETURN(&ptr, tmp, u8, &params.ed);

   err = scd_set_smbus_params(ctx, bus, &params);
   if (err == 0)
      return count;
   return err;
}

static ssize_t smbus_tweaks(struct device *dev, struct device_attribute *attr,
                            const char *buf, size_t count)
{
   ssize_t res;
   struct scd_context *ctx = get_context_for_dev(dev);

   if (!ctx) {
      return -ENODEV;
   }

   scd_lock(ctx);
   res = parse_lines(ctx, buf, count, parse_smbus_tweak);
   scd_unlock(ctx);
   return res;
}

static ssize_t scd_dump_smbus_tweaks(struct scd_context *ctx, char *buf, size_t max)
{
   const struct scd_smbus_master *master;
   const struct scd_smbus *bus;
   const struct bus_params *params;
   ssize_t count = 0;

   list_for_each_entry(master, &ctx->smbus_master_list, list) {
      list_for_each_entry(bus, &master->bus_list, list) {
         list_for_each_entry(params, &bus->params, list) {
            count += scnprintf(buf + count, max - count,
                  "%d/%d/%02x: adap=%d t=%d datr=%d datw=%d ed=%d\n",
                  master->id, bus->id, params->addr, bus->adap.nr,
                  params->t, params->datr, params->datw, params->ed);
            if (count == max) {
               return count;
            }
         }
      }
   }

   return count;
}

static ssize_t show_smbus_tweaks(struct device *dev, struct device_attribute *attr,
                                 char *buf)
{
   struct scd_context *ctx = get_context_for_dev(dev);
   ssize_t count;

   if (!ctx) {
      return -ENODEV;
   }

   scd_lock(ctx);
   count = scd_dump_smbus_tweaks(ctx, buf, PAGE_SIZE);
   scd_unlock(ctx);

   return count;
}

static DEVICE_ATTR(smbus_tweaks, S_IRUSR|S_IRGRP|S_IWUSR|S_IWGRP,
                   show_smbus_tweaks, smbus_tweaks);

static int scd_create_sysfs_files(struct scd_context *ctx) {
   int err;

   err = sysfs_create_file(get_scd_kobj(ctx), &dev_attr_new_object.attr);
   if (err) {
      dev_err(get_scd_dev(ctx), "could not create %s attribute: %d",
              dev_attr_new_object.attr.name, err);
      goto fail_new_object;
   }

   err = sysfs_create_file(get_scd_kobj(ctx), &dev_attr_smbus_tweaks.attr);
   if (err) {
      dev_err(get_scd_dev(ctx), "could not create %s attribute for smbus tweak: %d",
              dev_attr_smbus_tweaks.attr.name, err);
      goto fail_smbus_tweaks;
   }

   return 0;

fail_smbus_tweaks:
   sysfs_remove_file(get_scd_kobj(ctx), &dev_attr_new_object.attr);
fail_new_object:
   return err;
}

static int scd_ext_hwmon_probe(struct pci_dev *pdev, size_t mem_len)
{
   struct scd_context *ctx = get_context_for_pdev(pdev);
   int err;

   if (ctx) {
      scd_warn("this pci device has already been probed\n");
      return -EEXIST;
   }

   ctx = kzalloc(sizeof(*ctx), GFP_KERNEL);
   if (!ctx) {
      return -ENOMEM;
   }

   ctx->pdev = pdev;
   get_device(&pdev->dev);
   INIT_LIST_HEAD(&ctx->list);

   ctx->initialized = false;
   mutex_init(&ctx->mutex);

   ctx->res_size = mem_len;

   INIT_LIST_HEAD(&ctx->led_list);
   INIT_LIST_HEAD(&ctx->smbus_master_list);
   INIT_LIST_HEAD(&ctx->mdio_master_list);
   INIT_LIST_HEAD(&ctx->gpio_list);
   INIT_LIST_HEAD(&ctx->reset_list);
   INIT_LIST_HEAD(&ctx->xcvr_list);
   INIT_LIST_HEAD(&ctx->fan_group_list);

   kobject_get(&pdev->dev.kobj);

   module_lock();
   list_add_tail(&ctx->list, &scd_list);
   module_unlock();

   err = scd_create_sysfs_files(ctx);
   if (err) {
      goto fail_sysfs;
   }

   return 0;

fail_sysfs:
   module_lock();
   list_del(&ctx->list);
   module_unlock();

   kobject_put(&pdev->dev.kobj);
   kfree(ctx);
   put_device(&pdev->dev);

   return err;
}

static void scd_ext_hwmon_remove(struct pci_dev *pdev)
{
   struct scd_context *ctx = get_context_for_pdev(pdev);

   if (!ctx) {
      return;
   }

   scd_info("removing scd components\n");

   scd_lock(ctx);
   scd_smbus_remove_all(ctx);
   scd_mdio_remove_all(ctx);
   scd_led_remove_all(ctx);
   scd_gpio_remove_all(ctx);
   scd_reset_remove_all(ctx);
   scd_xcvr_remove_all(ctx);
   scd_fan_group_remove_all(ctx);
   scd_unlock(ctx);

   module_lock();
   list_del(&ctx->list);
   module_unlock();

   sysfs_remove_file(&pdev->dev.kobj, &dev_attr_new_object.attr);
   sysfs_remove_file(&pdev->dev.kobj, &dev_attr_smbus_tweaks.attr);

   kfree(ctx);

   kobject_put(&pdev->dev.kobj);
   put_device(&pdev->dev);
}

static int scd_ext_hwmon_finish_init(struct pci_dev *pdev)
{
   struct scd_context *ctx = get_context_for_pdev(pdev);

   if (!ctx) {
      return -ENODEV;
   }

   scd_lock(ctx);
   ctx->initialized = true;
   scd_unlock(ctx);
   return 0;
}

static struct scd_ext_ops scd_hwmon_ops = {
   .probe  = scd_ext_hwmon_probe,
   .remove = scd_ext_hwmon_remove,
   .finish_init = scd_ext_hwmon_finish_init,
};

static int __init scd_hwmon_init(void)
{
   int err = 0;

   scd_info("loading scd hwmon driver\n");
   mutex_init(&scd_hwmon_mutex);
   INIT_LIST_HEAD(&scd_list);

   err = scd_register_ext_ops(&scd_hwmon_ops);
   if (err) {
      scd_warn("scd_register_ext_ops failed\n");
      return err;
   }

   return err;
}

static void __exit scd_hwmon_exit(void)
{
   scd_info("unloading scd hwmon driver\n");
   scd_unregister_ext_ops();
}

module_init(scd_hwmon_init);
module_exit(scd_hwmon_exit);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Arista Networks");
MODULE_DESCRIPTION("SCD component driver");
