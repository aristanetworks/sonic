/* Copyright (c) 2024 Arista Networks, Inc.
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
 */

#include <linux/module.h>
#include <linux/moduleparam.h>
#include <linux/device.h>
#include <linux/hwmon.h>
#include <linux/hwmon-sysfs.h>
#include <linux/i2c.h>
#include <linux/slab.h>
#include <linux/workqueue.h>
#include <linux/leds.h>
#include <linux/version.h>

#define DRIVER_NAME "pali-fan-cpld"

#define LED_NAME_MAX_SZ 20
#define MAX_FAN_COUNT 5

#define MINOR_VERSION_REG  0x00
#define MAJOR_VERSION_REG  0x01
#define SCRATCHPAD_REG     0x02

#define FAN_BASE_REG(Id)           (0x10 * (1 + (Id)))
#define FAN_PWM_REG(Id)            ((FAN_BASE_REG(Id)))
#define FAN_TACH_REG_LOW(Id, Num)  ((FAN_BASE_REG(Id) + 1 + ((Num) * 2)))
#define FAN_TACH_REG_HIGH(Id, Num) ((FAN_BASE_REG(Id) + 2 + ((Num) * 2)))

#define FAN_ID_REG(Id)   (0x61 + (Id))
#define FAN_PRESENT_REG   0x70
#define FAN_OK_REG        0x71

#define FAN_BLUE_LED_REG  0x73
#define FAN_AMBER_LED_REG 0x74
#define FAN_GREEN_LED_REG 0x75
#define FAN_RED_LED_REG   0x76

#define FAN_INT_REG       0x77
#define FAN_ID_CHNG_REG   0x78
#define FAN_PRES_CHNG_REG 0x80
#define FAN_OK_CHNG_REG   0x82

#define FAN_INT_OK   BIT(0)
#define FAN_INT_PRES BIT(1)
#define FAN_INT_ID   BIT(2)

#define FAN_LED_GREEN BIT(0)
#define FAN_LED_RED   BIT(1)
#define FAN_LED_AMBER ((FAN_LED_GREEN) | (FAN_LED_RED))
#define FAN_LED_BLUE  BIT(2)

#define FAN_MAX_PWM 255

#define FAN_ID_MASK    0x1F
#define FAN_ID_UNKNOWN (FAN_ID_MASK + 1)

#define pali_dbg(cpld, ...) dev_dbg(&(cpld->client->dev), __VA_ARGS__)
#define pali_err(cpld, ...) dev_err(&(cpld->client->dev), __VA_ARGS__)
#define pali_info(cpld, ...) dev_info(&(cpld->client->dev), __VA_ARGS__)
#define pali_warn(cpld, ...) dev_warn(&(cpld->client->dev), __VA_ARGS__)

static bool safe_mode = true;
module_param(safe_mode, bool, S_IRUSR | S_IWUSR);
MODULE_PARM_DESC(safe_mode, "force fan speed to 100% during probe");

static bool managed_leds = true;
module_param(managed_leds, bool, S_IRUSR | S_IWUSR);
MODULE_PARM_DESC(managed_leds, "let the driver handle the leds");

static unsigned long poll_interval = 0;
module_param(poll_interval, ulong, S_IRUSR);
MODULE_PARM_DESC(poll_interval, "interval between two polling in ms");

static struct workqueue_struct *pali_cpld_workqueue;

enum cpld_type {
   PALI2_CPLD = 0,
};

struct cpld_info {
   u8 fan_count;
   u32 tach_hz;
};

struct cpld_fan_data {
   const struct fan_id *fan_id;
   struct led_classdev cdev;
   bool ok;
   bool present;
   bool forward;
   bool dual;
   u16 tach;
   u8 pwm;
   u8 ident;
   u8 index;
   char led_name[LED_NAME_MAX_SZ];
};

struct cpld_data {
   const struct cpld_info *info;
   struct mutex lock;
   struct i2c_client *client;
   struct device *hwmon_dev;
   struct delayed_work dwork;
   struct cpld_fan_data fans[MAX_FAN_COUNT];
   const struct attribute_group *groups[1 + MAX_FAN_COUNT + 1];
   u8 minor;
   u8 major;
   u8 present;
   u8 ok;
   u8 blue_led;
   u8 amber_led;
   u8 green_led;
   u8 red_led;
};

static const struct cpld_info cpld_infos[] = {
   [PALI2_CPLD] = {
      .fan_count = 4,
      .tach_hz = 100000,
   },
};

static const struct fan_id {
   const char *model;
   unsigned pulses;
} fan_ids[] = {
   [0b00000]        = { "FAN-7021H-RED",   2 },
   [0b00001]        = { "FAN-7021H-RED",   2 },
   [0b01000]        = { "FAN-7022HQ-RED",  2 },
   [0b01001]        = { "FAN-7022HQ-RED",  2 },
   [0b10000]        = { "FAN-7021H-BLUE",  2 },
   [0b10001]        = { "FAN-7021H-BLUE",  2 },
   [0b11000]        = { "FAN-7022HQ-BLUE", 2 },
   [0b11001]        = { "FAN-7022HQ-BLUE", 2 },
   [FAN_ID_UNKNOWN] = { "Unknown",         2 },
};

static struct cpld_fan_data *fan_from_cpld(struct cpld_data *cpld, u8 fan_id)
{
   return &cpld->fans[fan_id];
}

static struct cpld_fan_data *fan_from_dev(struct device *dev, u8 fan_id)
{
   struct cpld_data *cpld = dev_get_drvdata(dev);
   return fan_from_cpld(cpld, fan_id);
}

static s32 cpld_read_byte(struct cpld_data *cpld, u8 reg, u8 *res)
{
   int err;

   err = i2c_smbus_read_byte_data(cpld->client, reg);
   if (err < 0) {
      pali_err(cpld, "failed to read reg 0x%02x error=%d\n", reg, err);
      return err;
   }

   *res = (err & 0xff);

   return 0;
}

static s32 cpld_write_byte(struct cpld_data *cpld, u8 reg, u8 byte)
{
   int err;

   err = i2c_smbus_write_byte_data(cpld->client, reg, byte);
   if (err) {
      pali_err(cpld, "failed to write 0x%02x in reg 0x%02x error=%d\n", byte, reg, err);
   }

   return err;
}

static void cpld_work_start(struct cpld_data *cpld)
{
   if (poll_interval) {
      queue_delayed_work(pali_cpld_workqueue, &cpld->dwork,
                         msecs_to_jiffies(poll_interval));
   }
}

static s32 cpld_read_fan_id(struct cpld_data *cpld, u8 fan_id)
{
   struct cpld_fan_data *fan = fan_from_cpld(cpld, fan_id);
   s32 err;
   u8 tmp;

   err = cpld_read_byte(cpld, FAN_ID_REG(fan_id), &tmp);
   if (err)
      return err;

   fan->ident   = tmp & FAN_ID_MASK;
   fan->dual    = !((tmp >> 3) & 0x1);
   fan->forward = !((tmp >> 4) & 0x1);
   fan->fan_id  = &fan_ids[fan->ident];

   if (!fan->fan_id->model) {
      fan->fan_id = &fan_ids[FAN_ID_UNKNOWN];
      pali_warn(cpld, "Unknown fan id: 0x%02x", fan->ident);
   }

   return 0;
}

static int cpld_update_leds(struct cpld_data *cpld)
{
   struct cpld_fan_data *fan;
   int err;
   int i;

   cpld->blue_led = 0;
   cpld->amber_led = 0;
   cpld->green_led = 0;
   cpld->red_led = 0;

   for (i = 0; i < cpld->info->fan_count; ++i) {
      fan = fan_from_cpld(cpld, i);
      if (fan->ok && fan->present)
         cpld->green_led |= (1 << i);
      else
         cpld->red_led |= (1 << i);
   }

   err = cpld_write_byte(cpld, FAN_BLUE_LED_REG, cpld->blue_led);
   if (err)
      return err;

   err = cpld_write_byte(cpld, FAN_AMBER_LED_REG, cpld->amber_led);
   if (err)
      return err;

   err = cpld_write_byte(cpld, FAN_GREEN_LED_REG, cpld->green_led);
   if (err)
      return err;

   err = cpld_write_byte(cpld, FAN_RED_LED_REG, cpld->red_led);
   if (err)
      return err;

   return 0;
}

static int cpld_update(struct cpld_data *cpld)
{
   struct cpld_fan_data *fan;
   const char *str;
   int fans_connected = 0;
   int err;
   int i;
   u8 interrupt, id_chng, ok_chng, pres_chng;

   pali_dbg(cpld, "polling cpld information\n");

   err = cpld_read_byte(cpld, FAN_INT_REG, &interrupt);
   if (err)
      goto fail;

   if (interrupt & FAN_INT_ID) {
      err = cpld_read_byte(cpld, FAN_ID_CHNG_REG, &id_chng);
      if (err)
         goto fail;
   }

   if (interrupt & FAN_INT_OK) {
      err = cpld_read_byte(cpld, FAN_OK_CHNG_REG, &ok_chng);
      if (err)
         goto fail;
      err = cpld_read_byte(cpld, FAN_OK_REG, &cpld->ok);
      if (err)
         goto fail;
   }

   if (interrupt & FAN_INT_PRES) {
      err = cpld_read_byte(cpld, FAN_PRES_CHNG_REG, &pres_chng);
      if (err)
         goto fail;
      err = cpld_read_byte(cpld, FAN_OK_REG, &cpld->present);
      if (err)
         goto fail;
   }

   for (i = 0; i < cpld->info->fan_count; ++i) {
      fan = fan_from_cpld(cpld, i);

      if ((interrupt & FAN_INT_PRES) && (pres_chng & (1 << i))) {
         if (fan->present && (cpld->present & (1 << i))) {
            str = "hotswapped";
         } else if (!fan->present && (cpld->present & (1 << i))) {
            str = "plugged";
            fan->present = true;
         } else {
            str = "unplugged";
            fan->present = false;
         }
         pali_info(cpld, "fan %d was %s\n", i + 1, str);
      }

      if ((interrupt & FAN_INT_OK) && (ok_chng & (1 << i))) {
         if (fan->ok && (cpld->ok & (1 << i))) {
            pali_warn(cpld, "fan %d had a small snag\n", i + 1);
         } else if (fan->ok && !(cpld->ok & (1 << i))) {
            pali_warn(cpld, "fan %d is in fault, likely stuck\n", i + 1);
            fan->ok = false;
         } else {
            pali_info(cpld, "fan %d has recovered a running state\n", i + 1);
            fan->ok = true;
         }
      }

      if ((interrupt & FAN_INT_ID) && (id_chng & (1 << i))) {
         pali_info(cpld, "fan %d kind has changed\n", i + 1);
         cpld_read_fan_id(cpld, i);
      }

      if (fan->present)
         fans_connected += 1;
   }

   if (cpld->info->fan_count - fans_connected > 1) {
      pali_warn(cpld, "it is not recommended to have more than one fan "
               "unplugged. (%d/%d connected)\n",
               fans_connected, cpld->info->fan_count);
   }

   cpld_write_byte(cpld, FAN_ID_CHNG_REG, id_chng);
   cpld_write_byte(cpld, FAN_OK_CHNG_REG, ok_chng);
   cpld_write_byte(cpld, FAN_PRES_CHNG_REG, pres_chng);

   if (managed_leds)
      err = cpld_update_leds(cpld);

fail:
   return err;
}

static s32 cpld_write_pwm(struct cpld_data *cpld, u8 fan_id, u8 pwm)
{
   struct cpld_fan_data *fan = fan_from_cpld(cpld, fan_id);
   int err;

   err = cpld_write_byte(cpld, FAN_PWM_REG(fan_id), pwm);
   if (err)
      return err;

   fan->pwm = pwm;

   return 0;
}

static int cpld_read_present(struct cpld_data *cpld)
{
   struct cpld_fan_data *fan;
   int err;
   int i;

   err = cpld_read_byte(cpld, FAN_PRESENT_REG, &cpld->present);
   if (err)
      return err;

   for (i = 0; i < cpld->info->fan_count; ++i) {
      fan = fan_from_cpld(cpld, i);
      fan->present = !!(cpld->present & (1 << i));
   }

   return 0;
}

static int cpld_read_fault(struct cpld_data *cpld)
{
   struct cpld_fan_data *fan;
   int err;
   int i;

   err = cpld_read_byte(cpld, FAN_OK_REG, &cpld->ok);
   if (err)
      return err;

   for (i = 0; i < cpld->info->fan_count; ++i) {
      fan = fan_from_cpld(cpld, i);
      fan->ok = !!(cpld->ok & (1 << i));
   }

   return 0;
}

static s32 cpld_read_tach_single(struct cpld_data *cpld, u8 fan_id, u8 fan_num,
                                 u16 *tach)
{
   int err;
   u8 low;
   u8 high;

   err = cpld_read_byte(cpld, FAN_TACH_REG_LOW(fan_id, fan_num), &low);
   if (err)
      return err;

   err = cpld_read_byte(cpld, FAN_TACH_REG_HIGH(fan_id, fan_num), &high);
   if (err)
      return err;

   *tach = ((u16)high << 8) | low;

   return 0;
}

static s32 cpld_read_fan_tach(struct cpld_data *cpld, u8 fan_id)
{
   struct cpld_fan_data *fan = fan_from_cpld(cpld, fan_id);
   s32 err = 0;
   int i;

   /* read inner fan first id=1, then outer id=0 (when dual) */
   for (i = 1; i >= !fan->dual; i--) {
      err = cpld_read_tach_single(cpld, fan_id, i, &fan->tach);
      if (err)
         break;

      pali_dbg(cpld, "fan%d/%d tach=0x%04x\n", fan_id + 1, i + 1, fan->tach);
      if (fan->tach == 0xffff) {
         cpld_read_present(cpld);
         cpld_read_fault(cpld);
         if (managed_leds)
            cpld_update_leds(cpld);

         if (!fan->present)
            return -ENODEV;

         pali_warn(cpld,
            "Invalid tach information read from fan %d, this is likely "
            "a hardware issue (stuck fan or broken register)\n", fan_id + 1);

         return -EIO;
      }
   }

   return err;
}

static s32 cpld_read_fan_pwm(struct cpld_data *cpld, u8 fan_id)
{
   struct cpld_fan_data *fan = fan_from_cpld(cpld, fan_id);
   int err;
   u8 pwm;

   err = cpld_read_byte(cpld, FAN_PWM_REG(fan_id), &pwm);
   if (err)
      return err;

   fan->pwm = pwm;

   return 0;
}

static s32 cpld_read_fan_led(struct cpld_data *data, u8 fan_id, u8 *val)
{
   bool blue = data->blue_led & (1 << fan_id);
   bool amber = data->amber_led & (1 << fan_id);
   bool red = data->red_led & (1 << fan_id);
   bool green = data->green_led & (1 << fan_id);

   *val = 0;
   if (blue)
      *val |= FAN_LED_BLUE;
   if (amber)
      *val |= FAN_LED_AMBER;
   if (green)
      *val |= FAN_LED_GREEN;
   if (red)
      *val |= FAN_LED_RED;

   return 0;
}

static s32 cpld_write_fan_led(struct cpld_data *cpld, u8 fan_id, u8 val)
{
   int err = 0;

   if (val > 7)
      return -EINVAL;

   if (val & FAN_LED_BLUE)
      cpld->blue_led |= (1 << fan_id);
   else
      cpld->blue_led &= ~(1 << fan_id);

   if ((val & FAN_LED_AMBER) == FAN_LED_AMBER)
      cpld->amber_led |= (1 << fan_id);
   else
      cpld->amber_led &= ~(1 << fan_id);

   if (val & FAN_LED_GREEN && (val & FAN_LED_AMBER) != FAN_LED_AMBER)
      cpld->green_led |= (1 << fan_id);
   else
      cpld->green_led &= ~(1 << fan_id);

   if (val & FAN_LED_RED && (val & FAN_LED_AMBER) != FAN_LED_AMBER)
      cpld->red_led |= (1 << fan_id);
   else
      cpld->red_led &= ~(1 << fan_id);

   err = cpld_write_byte(cpld, FAN_BLUE_LED_REG, cpld->blue_led);
   if (err)
      return err;

   err = cpld_write_byte(cpld, FAN_AMBER_LED_REG, cpld->amber_led);
   if (err)
      return err;

   err = cpld_write_byte(cpld, FAN_GREEN_LED_REG, cpld->green_led);
   if (err)
      return err;

   err = cpld_write_byte(cpld, FAN_RED_LED_REG, cpld->red_led);

   return err;
}

static void brightness_set(struct led_classdev *led_cdev,
                           enum led_brightness val)
{
   struct cpld_fan_data *fan = container_of(led_cdev, struct cpld_fan_data,
                                            cdev);
   struct cpld_data *data = dev_get_drvdata(led_cdev->dev->parent);

   cpld_write_fan_led(data, fan->index, val);
}

static enum led_brightness brightness_get(struct led_classdev *led_cdev)
{
   struct cpld_fan_data *fan = container_of(led_cdev, struct cpld_fan_data,
                                            cdev);
   struct cpld_data *data = dev_get_drvdata(led_cdev->dev->parent);
   int err;
   u8 val;

   err = cpld_read_fan_led(data, fan->index, &val);
   if (err)
      return 0;

   return val;
}

static int led_init(struct cpld_fan_data *fan, struct i2c_client *client,
                    int fan_index)
{
   fan->index = fan_index;
   fan->cdev.brightness_set = brightness_set;
   fan->cdev.brightness_get = brightness_get;
   scnprintf(fan->led_name, LED_NAME_MAX_SZ, "fan%d", fan->index + 1);
   fan->cdev.name = fan->led_name;

   return led_classdev_register(&client->dev, &fan->cdev);
}

static void cpld_leds_unregister(struct cpld_data *cpld, int num_leds)
{
   int i = 0;
   struct cpld_fan_data *fan;

   for (i = 0; i < num_leds; i++) {
      fan = fan_from_cpld(cpld, i);
      led_classdev_unregister(&fan->cdev);
   }
}

static ssize_t cpld_fan_pwm_show(struct device *dev, struct device_attribute *da,
                                 char *buf)
{
   struct sensor_device_attribute *attr = to_sensor_dev_attr(da);
   struct cpld_data *cpld = dev_get_drvdata(dev);
   struct cpld_fan_data *fan = fan_from_cpld(cpld, attr->index);
   int err;

   mutex_lock(&cpld->lock);
   err = cpld_read_fan_pwm(cpld, attr->index);
   mutex_unlock(&cpld->lock);
   if (err)
      return err;

   return sprintf(buf, "%hhu\n", fan->pwm);
}

static ssize_t cpld_fan_pwm_store(struct device *dev, struct device_attribute *da,
                                  const char *buf, size_t count)
{
   struct sensor_device_attribute *attr = to_sensor_dev_attr(da);
   struct cpld_data *cpld = dev_get_drvdata(dev);
   u8 val;
   int err;

   if (sscanf(buf, "%hhu", &val) != 1)
      return -EINVAL;

   mutex_lock(&cpld->lock);
   err = cpld_write_pwm(cpld, attr->index, val);
   mutex_unlock(&cpld->lock);
   if (err)
      return err;

   return count;
}

static ssize_t cpld_fan_present_show(struct device *dev,
                                     struct device_attribute *da,
                                     char *buf)
{
   struct sensor_device_attribute *attr = to_sensor_dev_attr(da);
   struct cpld_data *cpld = dev_get_drvdata(dev);
   struct cpld_fan_data *fan = fan_from_cpld(cpld, attr->index);
   int err;

   if (!poll_interval) {
      mutex_lock(&cpld->lock);
      err = cpld_read_present(cpld);
      mutex_unlock(&cpld->lock);
      if (err)
         return err;
   }

   return sprintf(buf, "%d\n", fan->present);
}

static ssize_t cpld_fan_id_show(struct device *dev, struct device_attribute *da,
                                char *buf)
{
   struct sensor_device_attribute *attr = to_sensor_dev_attr(da);
   struct cpld_data *cpld = dev_get_drvdata(dev);
   struct cpld_fan_data *fan = fan_from_cpld(cpld, attr->index);
   int err = 0;

   if (!poll_interval) {
      mutex_lock(&cpld->lock);
      err = cpld_read_fan_id(cpld, attr->index);
      mutex_unlock(&cpld->lock);
      if (err)
         return err;
   }

   return sprintf(buf, "%hhu\n", fan->ident);
}

static ssize_t cpld_fan_fault_show(struct device *dev, struct device_attribute *da,
                                   char *buf)
{
   struct sensor_device_attribute *attr = to_sensor_dev_attr(da);
   struct cpld_data *cpld = dev_get_drvdata(dev);
   struct cpld_fan_data *fan = fan_from_cpld(cpld, attr->index);
   int err;

   if (!poll_interval) {
      mutex_lock(&cpld->lock);
      err = cpld_read_fault(cpld);
      mutex_unlock(&cpld->lock);
      if (err)
         return err;
   }

   return sprintf(buf, "%d\n", !fan->ok);
}

static ssize_t cpld_fan_tach_show(struct device *dev, struct device_attribute *da,
                                  char *buf)
{
   struct sensor_device_attribute *attr = to_sensor_dev_attr(da);
   struct cpld_data *cpld = dev_get_drvdata(dev);
   struct cpld_fan_data *fan = fan_from_cpld(cpld, attr->index);
   int err;
   int rpms;

   mutex_lock(&cpld->lock);
   err = cpld_read_fan_tach(cpld, attr->index);
   mutex_unlock(&cpld->lock);
   if (err)
      return err;

   if (!fan->tach) {
      return -EINVAL;
   }

   rpms = ((cpld->info->tach_hz * 60) / fan->tach) / fan->fan_id->pulses;

   return sprintf(buf, "%d\n", rpms);
}

static ssize_t cpld_fan_led_show(struct device *dev, struct device_attribute *da,
                                 char *buf)
{
   struct sensor_device_attribute *attr = to_sensor_dev_attr(da);
   struct cpld_data *cpld = dev_get_drvdata(dev);
   int err;
   u8 val;

   err = cpld_read_fan_led(cpld, attr->index, &val);
   if (err)
      return err;

   return sprintf(buf, "%hhu\n", val);
}

static ssize_t cpld_fan_led_store(struct device *dev, struct device_attribute *da,
                                  const char *buf, size_t count)
{
   struct sensor_device_attribute *attr = to_sensor_dev_attr(da);
   struct cpld_data *cpld = dev_get_drvdata(dev);
   int err;
   u8 val;

   if (managed_leds)
      return -EPERM;

   if (sscanf(buf, "%hhu", &val) != 1)
      return -EINVAL;

   mutex_lock(&cpld->lock);
   err = cpld_write_fan_led(cpld, attr->index, val);
   mutex_unlock(&cpld->lock);
   if (err)
      return err;

   return count;
}

static ssize_t cpld_fan_airflow_show(struct device *dev,
                                     struct device_attribute *da,
                                     char *buf)
{
   struct sensor_device_attribute *attr = to_sensor_dev_attr(da);
   struct cpld_fan_data *fan = fan_from_dev(dev, attr->index);
   return sprintf(buf, "%s\n", (fan->forward) ? "forward" : "reverse");
}

static ssize_t cpld_fan_model_show(struct device *dev,
                                   struct device_attribute *da,
                                   char *buf)
{
   struct sensor_device_attribute *attr = to_sensor_dev_attr(da);
   struct cpld_fan_data *fan = fan_from_dev(dev, attr->index);
   return sprintf(buf, "%s\n", (fan->present) ? fan->fan_id->model : "Not present");
}

#define FAN_DEVICE_ATTR(_name)                                                \
   static SENSOR_DEVICE_ATTR(pwm## _name, S_IRUGO|S_IWGRP|S_IWUSR,            \
                             cpld_fan_pwm_show, cpld_fan_pwm_store, _name-1); \
   static SENSOR_DEVICE_ATTR(fan##_name##_id, S_IRUGO,                        \
                             cpld_fan_id_show, NULL, _name-1);                \
   static SENSOR_DEVICE_ATTR(fan##_name##_input, S_IRUGO,                     \
                             cpld_fan_tach_show, NULL, _name-1);              \
   static SENSOR_DEVICE_ATTR(fan##_name##_fault, S_IRUGO,                     \
                             cpld_fan_fault_show, NULL, _name-1);             \
   static SENSOR_DEVICE_ATTR(fan##_name##_present, S_IRUGO,                   \
                             cpld_fan_present_show, NULL, _name-1);           \
   static SENSOR_DEVICE_ATTR(fan##_name##_led, S_IRUGO|S_IWGRP|S_IWUSR,       \
                             cpld_fan_led_show, cpld_fan_led_store, _name-1); \
   static SENSOR_DEVICE_ATTR(fan##_name##_airflow, S_IRUGO,                   \
                             cpld_fan_airflow_show, NULL, _name-1);           \
   static SENSOR_DEVICE_ATTR(fan##_name##_model, S_IRUGO,                     \
                             cpld_fan_model_show, NULL, _name-1);

#define FAN_ATTR(_name)                                  \
    &sensor_dev_attr_pwm##_name.dev_attr.attr,           \
    &sensor_dev_attr_fan##_name##_id.dev_attr.attr,      \
    &sensor_dev_attr_fan##_name##_input.dev_attr.attr,   \
    &sensor_dev_attr_fan##_name##_fault.dev_attr.attr,   \
    &sensor_dev_attr_fan##_name##_present.dev_attr.attr, \
    &sensor_dev_attr_fan##_name##_led.dev_attr.attr,     \
    &sensor_dev_attr_fan##_name##_airflow.dev_attr.attr, \
    &sensor_dev_attr_fan##_name##_model.dev_attr.attr


#define FAN_ATTR_GROUP(_name) &fan##_name##_attr_group

#define DEVICE_FAN_ATTR_GROUP(_name)                                          \
   FAN_DEVICE_ATTR(_name);                                                    \
   static struct attribute *fan##_name##_attrs[] = { FAN_ATTR(_name), NULL }; \
   static struct attribute_group fan##_name##_attr_group = {                  \
      .attrs = fan##_name##_attrs,                                            \
   }

DEVICE_FAN_ATTR_GROUP(1);
DEVICE_FAN_ATTR_GROUP(2);
DEVICE_FAN_ATTR_GROUP(3);
DEVICE_FAN_ATTR_GROUP(4);
DEVICE_FAN_ATTR_GROUP(5);
DEVICE_FAN_ATTR_GROUP(6);
DEVICE_FAN_ATTR_GROUP(7);
DEVICE_FAN_ATTR_GROUP(8);

static struct attribute_group *fan_groups[] = {
   FAN_ATTR_GROUP(1),
   FAN_ATTR_GROUP(2),
   FAN_ATTR_GROUP(3),
   FAN_ATTR_GROUP(4),
   FAN_ATTR_GROUP(5),
   FAN_ATTR_GROUP(6),
   FAN_ATTR_GROUP(7),
   FAN_ATTR_GROUP(8),
   NULL,
};

static ssize_t cpld_revision_show(struct device *dev, struct device_attribute *attr,
                                  char *buf)
{
   struct cpld_data *cpld = dev_get_drvdata(dev);
   return sprintf(buf, "%02x.%02x\n", cpld->major, cpld->minor);
}

DEVICE_ATTR(cpld_revision, S_IRUGO, cpld_revision_show, NULL);

static ssize_t cpld_update_show(struct device *dev, struct device_attribute *attr,
                                char *buf)
{
   struct cpld_data *cpld = dev_get_drvdata(dev);
   int err;

   mutex_lock(&cpld->lock);
   err = cpld_update(cpld);
   mutex_unlock(&cpld->lock);

   return err;
}

DEVICE_ATTR(update, S_IRUGO, cpld_update_show, NULL);

static struct attribute *cpld_attrs[] = {
    &dev_attr_cpld_revision.attr,
    &dev_attr_update.attr,
    NULL,
};

static struct attribute_group cpld_group = {
   .attrs = cpld_attrs,
};

static void cpld_work_fn(struct work_struct *work)
{
   struct delayed_work *dwork = to_delayed_work(work);
   struct cpld_data *cpld = container_of(dwork, struct cpld_data, dwork);

   mutex_lock(&cpld->lock);
   cpld_update(cpld);
   cpld_work_start(cpld);
   mutex_unlock(&cpld->lock);
}

static int cpld_init(struct cpld_data *cpld)
{
   struct cpld_fan_data *fan;
   int err;
   int i;

   err = cpld_read_byte(cpld, MINOR_VERSION_REG, &cpld->minor);
   if (err)
      return -ENODEV;

   err = cpld_read_byte(cpld, MAJOR_VERSION_REG, &cpld->major);
   if (err)
      return err;

   pali_info(cpld, "pali CPLD version %02x.%02x\n", cpld->major, cpld->minor);

   err = cpld_read_byte(cpld, FAN_PRESENT_REG, &cpld->present);
   if (err)
      return err;

   err = cpld_read_byte(cpld, FAN_OK_REG, &cpld->ok);
   if (err)
      return err;

   for (i = 0; i < cpld->info->fan_count; ++i) {
      fan = fan_from_cpld(cpld, i);
      fan->present = !!(cpld->present & (1 << i));
      fan->ok = !!(cpld->ok & (1 << i));
      if (fan->present) {
         cpld_read_fan_id(cpld, i);
         cpld_read_fan_tach(cpld, i);
         cpld_read_fan_pwm(cpld, i);
         if (safe_mode)
            cpld_write_pwm(cpld, i, FAN_MAX_PWM);
         err = led_init(fan, cpld->client, i);
         if (err) {
            cpld_leds_unregister(cpld, i);
            return err;
         }
      }
   }

   cpld_write_byte(cpld, FAN_OK_CHNG_REG, 0x00);
   cpld_write_byte(cpld, FAN_PRES_CHNG_REG, 0x00);
   cpld_write_byte(cpld, FAN_ID_CHNG_REG, 0x00);

   if (managed_leds) {
      err = cpld_update_leds(cpld);
      if (err)
         return err;
   }

   INIT_DELAYED_WORK(&cpld->dwork, cpld_work_fn);
   cpld_work_start(cpld);

   return err;
}

#if LINUX_VERSION_CODE < KERNEL_VERSION(6, 0, 0)
static int
#else
static void
#endif
cpld_remove(struct i2c_client *client)
{
   struct cpld_data *cpld = i2c_get_clientdata(client);

   mutex_lock(&cpld->lock);
   cancel_delayed_work_sync(&cpld->dwork);
   mutex_unlock(&cpld->lock);

   cpld_leds_unregister(cpld, cpld->info->fan_count);

#if LINUX_VERSION_CODE < KERNEL_VERSION(6, 0, 0)
   return 0;
#endif
}

static int cpld_probe(struct i2c_client *client,
                      const struct i2c_device_id *id)
{
   struct device *dev = &client->dev;
   struct device *hwmon_dev;
   struct cpld_data *cpld;
   int err;
   int i;

   if (!i2c_check_functionality(client->adapter, I2C_FUNC_SMBUS_BYTE_DATA)) {
      pali_err(cpld, "adapter doesn't support byte transactions\n");
      return -ENODEV;
   }

   cpld = devm_kzalloc(dev, sizeof(*cpld), GFP_KERNEL);
   if (!cpld)
      return -ENOMEM;

   i2c_set_clientdata(client, cpld);
   cpld->client = client;

   cpld->info = &cpld_infos[id->driver_data];
   mutex_init(&cpld->lock);

   cpld->groups[0] = &cpld_group;
   for (i = 0; i < cpld->info->fan_count; ++i) {
      cpld->groups[i + 1] = fan_groups[i];
   }

   mutex_lock(&cpld->lock);
   err = cpld_init(cpld);
   mutex_unlock(&cpld->lock);
   if (err)
      return err;

   hwmon_dev = devm_hwmon_device_register_with_groups(dev, client->name,
                                                      cpld, cpld->groups);
   if (IS_ERR(hwmon_dev)) {
      cpld_remove(client);
      return PTR_ERR(hwmon_dev);
   }

   cpld->hwmon_dev = hwmon_dev;

   return err;
}

static const struct i2c_device_id cpld_id[] = {
   { "pali2_cpld", PALI2_CPLD },
   {}
};

MODULE_DEVICE_TABLE(i2c, cpld_id);

static struct i2c_driver cpld_driver = {
   .class = I2C_CLASS_HWMON,
   .driver = {
      .name = DRIVER_NAME,
   },
   .id_table = cpld_id,
   .probe = cpld_probe,
   .remove = cpld_remove,
};

static int __init pali_cpld_init(void)
{
   int err;

   pali_cpld_workqueue = create_singlethread_workqueue(DRIVER_NAME);
   if (IS_ERR_OR_NULL(pali_cpld_workqueue)) {
      pr_err("failed to initialize workqueue\n");
      return PTR_ERR(pali_cpld_workqueue);
   }

   err = i2c_add_driver(&cpld_driver);
   if (err < 0) {
      destroy_workqueue(pali_cpld_workqueue);
      pali_cpld_workqueue = NULL;
      return err;
   }

   return 0;
}

static void __exit pali_cpld_exit(void)
{
   i2c_del_driver(&cpld_driver);
   destroy_workqueue(pali_cpld_workqueue);
   pali_cpld_workqueue = NULL;
}

module_init(pali_cpld_init);
module_exit(pali_cpld_exit);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Arista Networks");
MODULE_DESCRIPTION("Pali fan cpld");
