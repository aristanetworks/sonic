// SPDX-License-Identifier: GPL-2.0-only
/*
 * Copyright (c) 2026 Arista Networks, Inc.
 *
 * Apply and verify AMD PCIe error settings through SMN and PCI configuration
 * accesses when requested through the apply_policy sysfs attribute.
 */

#define pr_fmt(fmt) KBUILD_MODNAME ": " fmt

#include <linux/bitmap.h>
#include <linux/device.h>
#include <linux/err.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/pci.h>
#include <linux/pci_regs.h>
#include <linux/sysfs.h>
#include <linux/version.h>

#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 16, 0)
#include <asm/amd/node.h>
#else
#include <asm/amd_nb.h>
#endif
#include <asm/cpufeature.h>
#include <asm/processor.h>

#define FATAL_ACTION_MASK 0x18
#define SMN_PORT_STRIDE 0x20
#define SMN_SECOND_REGISTER 0x0c

struct amd_policy_profile {
   const char *name;
   u8 family;
   u8 model;
   u16 root_device;
   u32 base;
   unsigned int ports;
};

static const struct amd_policy_profile profiles[] = {
   { "V3000",     0x19, 0x44, 0x14b5, 0x13b20118, 13 },
   { "Snowy Owl", 0x17, 0x01, 0x1450, 0x13b20180, 16 },
   { "Fire Range", 0x1a, 0x44, 0x14d8, 0x13b200f0, 18 },
};

struct root_port_setting {
   const char *name;
   u16 capability;
   u16 offset;
   unsigned int size;
   u32 mask;
   u32 value;
};

static const struct root_port_setting root_port_settings[] = {
   /* Unmask Completion Timeout in the AER Uncorrectable Error Mask. */
   { "AER", PCI_EXT_CAP_ID_ERR, PCI_ERR_UNCOR_MASK, 4,
     PCI_ERR_UNC_COMP_TIME, 0 },
   /* DPC Completion Control; preserve the firmware's Trigger Enable field. */
   { "DPC", PCI_EXT_CAP_ID_DPC, PCI_EXP_DPC_CTL, 2, BIT(2), BIT(2) },
};

struct amd_policy {
   const struct amd_policy_profile *profile;
   bool applied;
};

static struct amd_policy policy;
/* Serialize sysfs requests and protect the last application result. */
static DEFINE_MUTEX(apply_mutex);

/*
 * Apply masked updates through the AMD SMN APIs and verify the readback.
 * Only use for ordinary read/write control registers, without W1C side effects.
 * The AMD APIs serialize individual accesses, not this entire read/modify/write
 * sequence against other kernel clients.
 */
static int arista_smn_update_bits(u16 node, u32 address, u32 mask, u32 value)
{
   u32 before = 0, expected, readback = 0;
   int err;

   if (address & 3)
      return -EINVAL;

   err = pcibios_err_to_errno(amd_smn_read(node, address, &before));
   if (err)
      return err;
   if (PCI_POSSIBLE_ERROR(before))
      return -ENODEV;

   expected = (before & ~mask) | (value & mask);
   if (before != expected) {
      err = pcibios_err_to_errno(amd_smn_write(node, address, expected));
      if (err)
         return err;
   }

   err = pcibios_err_to_errno(amd_smn_read(node, address, &readback));
   if (err)
      return err;
   if (PCI_POSSIBLE_ERROR(readback))
      return -ENODEV;
   if (readback != expected) {
      pr_warn("SMN node %u address %#x: expected %#x, read back %#x\n",
              node, address, expected, readback);
      return -EIO;
   }
   pr_debug("SMN node %u address %#x: before %#x, read back %#x\n",
             node, address, before, readback);
   return 0;
}

static const struct amd_policy_profile *find_profile(void)
{
   unsigned int i;

   if (boot_cpu_data.x86_vendor != X86_VENDOR_AMD ||
       boot_cpu_has(X86_FEATURE_HYPERVISOR))
      return NULL;

   for (i = 0; i < ARRAY_SIZE(profiles); i++) {
      if (boot_cpu_data.x86 == profiles[i].family &&
          boot_cpu_data.x86_model == profiles[i].model)
         return &profiles[i];
   }
   return NULL;
}

static struct pci_dev *get_root(const struct amd_policy_profile *profile)
{
   struct pci_dev *root = pci_get_domain_bus_and_slot(0, 0, PCI_DEVFN(0, 0));
   u32 identity;
   int err;

   /* Check the expected host bridge at 0000:00:00.0 before SMN access. */
   if (!root) {
      err = -ENODEV;
      goto put_root;
   }

   err = pcibios_err_to_errno(pci_read_config_dword(root, PCI_VENDOR_ID,
                                                  &identity));
   if (err)
      goto put_root;
   if (identity != ((u32)profile->root_device << 16 | PCI_VENDOR_ID_AMD)) {
      err = -ENODEV;
      goto put_root;
   }
   return root;

put_root:
   pci_dev_put(root);
   return ERR_PTR(err);
}

static int configure_root_port(struct pci_dev *pdev, u16 capability,
                              const struct root_port_setting *setting)
{
   unsigned int offset = capability + setting->offset;
   u32 before, expected, readback;
   u16 word = 0;
   int err;

   if (offset + setting->size > PCI_CFG_SPACE_EXP_SIZE)
      return -EIO;

   if (setting->size == 2) {
      err = pci_read_config_word(pdev, offset, &word);
      before = word;
   } else {
      err = pci_read_config_dword(pdev, offset, &before);
   }
   if (err)
      return pcibios_err_to_errno(err);
   /* An all-masked AER register is valid; all-ones DPC reads are not. */
   if (setting->size == 2 && before == 0xffff)
      return -ENODEV;

   expected = (before & ~setting->mask) | (setting->value & setting->mask);
   if (before != expected) {
      if (setting->size == 2)
         err = pci_write_config_word(pdev, offset, expected);
      else
         err = pci_write_config_dword(pdev, offset, expected);
      if (err)
         return pcibios_err_to_errno(err);
   }

   if (setting->size == 2) {
      err = pci_read_config_word(pdev, offset, &word);
      readback = word;
   } else {
      err = pci_read_config_dword(pdev, offset, &readback);
   }
   if (err)
      return pcibios_err_to_errno(err);

   if (setting->size == 2 && readback == 0xffff)
      return -ENODEV;
   if (readback != expected) {
      pci_err(pdev, "%s verification failed: expected=%#x readback=%#x\n",
              setting->name, expected, readback);
      return -EIO;
   }
   pci_dbg(pdev, "%s before=%#x expected=%#x readback=%#x\n",
           setting->name, before, expected, readback);
   return 0;
}

/*
 * Validate the entire capability chain before configuring any settings.
 * Keep absent capabilities distinct from read errors or a corrupt chain;
 * pci_find_ext_capability() returns zero for all of these cases.
 */
static void apply_root_port_policy(struct pci_dev *pdev, unsigned int *failures,
                                   unsigned int *skips)
{
   DECLARE_BITMAP(visited, PCI_CFG_SPACE_EXP_SIZE / 4);
   u16 capabilities[ARRAY_SIZE(root_port_settings)] = { 0 };
   unsigned int offset = PCI_CFG_SPACE_SIZE;
   unsigned int i;
   u32 header;
   int err;

   bitmap_zero(visited, PCI_CFG_SPACE_EXP_SIZE / 4);
   while (offset) {
      if (offset < PCI_CFG_SPACE_SIZE ||
          offset > PCI_CFG_SPACE_EXP_SIZE - 4 || (offset & 3) ||
          test_and_set_bit(offset / 4, visited)) {
         err = -EIO;
         goto discovery_failed;
      }

      err = pcibios_err_to_errno(pci_read_config_dword(pdev, offset, &header));
      if (err)
         goto discovery_failed;
      if (!header && offset == PCI_CFG_SPACE_SIZE)
         break;
      if (!header || PCI_EXT_CAP_ID(header) == 0xffff) {
         err = -EIO;
         goto discovery_failed;
      }

      for (i = 0; i < ARRAY_SIZE(root_port_settings); i++) {
         if (!capabilities[i] &&
             PCI_EXT_CAP_ID(header) == root_port_settings[i].capability)
            capabilities[i] = offset;
      }
      offset = PCI_EXT_CAP_NEXT(header);
   }

   for (i = 0; i < ARRAY_SIZE(root_port_settings); i++) {
      if (!capabilities[i]) {
         (*skips)++;
         continue;
      }
      err = configure_root_port(pdev, capabilities[i], &root_port_settings[i]);
      if (err) {
         (*failures)++;
         pci_err(pdev, "%s policy failed: %d\n",
                 root_port_settings[i].name, err);
      }
   }
   return;

discovery_failed:
   *failures += ARRAY_SIZE(root_port_settings);
   pci_err(pdev, "PCIe policy capability discovery failed: %d\n", err);
}

static int apply_policy(const struct amd_policy_profile *profile)
{
   struct pci_dev *root;
   struct pci_dev *pdev = NULL;
   struct device *dev;
   unsigned int smn_failures = 0, root_failures = 0, skips = 0;
   unsigned int roots = 0, port, reg;
   int err;

   if (!profile)
      return 0;

   /* Revalidate on every trigger, including explicit reapplication. */
   root = get_root(profile);
   if (IS_ERR(root)) {
      err = PTR_ERR(root);
      pr_err("AMD root identity mismatch at 0000:00:00.0: %d\n", err);
      return err;
   }
   dev = &root->dev;

   /*
    * Attempt every update and report aggregate failure; successful writes are
    * retained if another register fails.
    */
   for (port = 0; port < profile->ports; port++) {
      for (reg = 0; reg < 2; reg++) {
         u32 address = profile->base + port * SMN_PORT_STRIDE +
                       reg * SMN_SECOND_REGISTER;

         err = arista_smn_update_bits(0, address, FATAL_ACTION_MASK, 0);
         if (err) {
            smn_failures++;
            dev_err(dev, "SMN profile=%s port=%u address=%#x failed: %d\n",
                    profile->name, port, address, err);
         } else {
            dev_dbg(dev, "SMN profile=%s port=%u address=%#x verified\n",
                    profile->name, port, address);
         }
      }
   }

   for_each_pci_dev(pdev) {
      if (pdev->vendor != PCI_VENDOR_ID_AMD ||
          pdev->class != (PCI_CLASS_BRIDGE_PCI << 8) ||
          !pci_is_pcie(pdev) || pci_pcie_type(pdev) != PCI_EXP_TYPE_ROOT_PORT)
         continue;

      roots++;
      apply_root_port_policy(pdev, &root_failures, &skips);
   }
   if (!roots) {
      dev_err(dev, "No AMD PCIe root ports found\n");
      root_failures++;
   }

   dev_info(dev, "profile=%s SMN: %u succeeded, %u failed; "
            "root ports=%u: %u failed, %u settings skipped\n",
            profile->name, profile->ports * 2 - smn_failures, smn_failures,
            roots, root_failures, skips);
   pci_dev_put(root);
   return smn_failures || root_failures ? -EIO : 0;
}

static ssize_t profile_show(struct module_attribute *attr,
                            struct module_kobject *mk, char *buf)
{
   return sysfs_emit(buf, "%s\n", policy.profile ? policy.profile->name : "none");
}

static ssize_t apply_policy_show(struct module_attribute *attr,
                                 struct module_kobject *mk, char *buf)
{
   ssize_t count;

   mutex_lock(&apply_mutex);
   count = sysfs_emit(buf, "%u\n", policy.applied);
   mutex_unlock(&apply_mutex);
   return count;
}

static ssize_t apply_policy_store(struct module_attribute *attr,
                                  struct module_kobject *mk, const char *buf,
                                  size_t count)
{
   int err;

   if (!sysfs_streq(buf, "1"))
      return -EINVAL;
   if (mutex_lock_interruptible(&apply_mutex))
      return -ERESTARTSYS;

   /* Always reapply on a trigger; only a fully verified pass marks success. */
   policy.applied = false;
   err = apply_policy(policy.profile);
   policy.applied = policy.profile && !err;
   mutex_unlock(&apply_mutex);
   if (err)
      return err;
   return count;
}

static struct module_attribute apply_policy_attr =
   __ATTR(apply_policy, 0644, apply_policy_show, apply_policy_store);

static struct module_attribute profile_attr =
   __ATTR(profile, 0444, profile_show, NULL);

static struct attribute *policy_attrs[] = {
   &profile_attr.attr,
   &apply_policy_attr.attr,
   NULL,
};

static umode_t policy_attr_is_visible(struct kobject *kobj,
                                     struct attribute *attr, int index)
{
   if (attr == &apply_policy_attr.attr && !policy.profile)
      return 0;
   return attr->mode;
}

static const struct attribute_group policy_attr_group = {
   .attrs = policy_attrs,
   .is_visible = policy_attr_is_visible,
};

static int __init amd_policy_init(void)
{
   struct pci_dev *root;
   int err;

   policy.profile = find_profile();
   if (policy.profile) {
      root = get_root(policy.profile);
      if (IS_ERR(root)) {
         err = PTR_ERR(root);
         pr_err("AMD PCIe policy: invalid root at 0000:00:00.0 for %s: %d\n",
                policy.profile->name, err);
         return err;
      }
      pci_dev_put(root);
   }

   err = sysfs_create_group(&THIS_MODULE->mkobj.kobj, &policy_attr_group);
   if (err)
      return err;
   pr_info("profile=%s ready at /sys/module/%s/profile\n",
            policy.profile ? policy.profile->name : "none", KBUILD_MODNAME);
   return 0;
}

static void __exit amd_policy_exit(void)
{
   sysfs_remove_group(&THIS_MODULE->mkobj.kobj, &policy_attr_group);
}

module_init(amd_policy_init);
module_exit(amd_policy_exit);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Arista Networks");
MODULE_DESCRIPTION("AMD PCIe SMN, AER and DPC error policy for Arista platforms");
