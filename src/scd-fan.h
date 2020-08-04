/* Copyright (c) 2018 Arista Networks, Inc.
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

#ifndef _LINUX_DRIVER_SCD_FAN_H_
#define _LINUX_DRIVER_SCD_FAN_H_

/* Fan info is for each fan slot */
enum fan_info_type {
   FAN_7011H_F = 0b000111,
   FAN_7011S_F = 0b001101,
   FAN_7011M_F = 0b001110,
   NOT_PRESENT_40 = 0b011111,
   FAN_7011H_R = 0b010111,
   FAN_7011S_R = 0b011101,
   FAN_7011M_R = 0b011110,
   NOT_PRESENT_80 = 0b111111,
};

struct fan_info {
   enum fan_info_type id;
   u32 hz;
   u8 fans;
   u8 rotors;
   u8 pulses;
   bool forward;
   bool present;
};

/* List of fan infos for platform 3 */
const static struct fan_info p3_fan_infos[] = {
   {
      .id = FAN_7011H_F,
      .hz = 100000,
      .fans = 2,
      .rotors = 2,
      .pulses = 2,
      .forward = true,
      .present = true,
   },
   {
      .id = FAN_7011S_F,
      .hz = 100000,
      .fans = 2,
      .rotors = 1,
      .pulses = 2,
      .forward = true,
      .present = true,
   },
   {
      .id = FAN_7011M_F,
      .hz = 100000,
      .fans = 2,
      .rotors = 1,
      .pulses = 2,
      .forward = true,
      .present = true,
   },
   {
      .id = FAN_7011H_R,
      .hz = 100000,
      .fans = 2,
      .rotors = 2,
      .pulses = 2,
      .forward = false,
      .present = true,
   },
   {
      .id = FAN_7011S_R,
      .hz = 100000,
      .fans = 2,
      .rotors = 1,
      .pulses = 2,
      .forward = false,
      .present = true,
   },
   {
      .id = FAN_7011M_R,
      .hz = 100000,
      .fans = 2,
      .rotors = 1,
      .pulses = 2,
      .forward = false,
      .present = true,
   },
   {
      .id = NOT_PRESENT_40,
      .hz = 100000,
      .fans = 2,
      .rotors = 1,
      .pulses = 2,
      .forward = true,
      .present = false,
   },
   {
      .id = NOT_PRESENT_80,
      .hz = 100000,
      .fans = 2,
      .rotors = 1,
      .pulses = 2,
      .forward = true,
      .present = false,
   },
};

/* For each fan platform, there are multiple fan slots */
struct fan_platform {
   u32 id;
   size_t max_fan_count;
   size_t max_attr_count;
   const struct fan_info *fan_infos;
   size_t fan_info_count;

   u32 id_offset;
   u32 id_step;

   u32 platform_offset;
   u32 present_offset;
   u32 ok_offset;
   u32 green_led_offset;
   u32 red_led_offset;

   u32 speed_offset;
   u32 speed_step;
   u32 speed_pwm_offset;
   u32 speed_tach_outer_offset;
   u32 speed_tach_inner_offset;

   u32 mask_platform;
   u32 mask_id;
   u32 mask_pwm;
   u32 mask_tach;
   u32 mask_green_led;
   u32 mask_red_led;
};

/* List of fan platforms */
static const struct fan_platform fan_platforms[] = {
   {
      .id = 3,
      .max_fan_count = 4,
      .max_attr_count = 7,
      .fan_infos = p3_fan_infos,
      .fan_info_count = ARRAY_SIZE(p3_fan_infos),

      .id_offset = 0x180,
      .id_step = 0x10,

      .platform_offset = 0x0,
      .present_offset = 0x1c0,
      .ok_offset = 0x1d0,
      .green_led_offset = 0x1e0,
      .red_led_offset = 0x1f0,

      .speed_offset = 0x10,
      .speed_step = 0x30,
      .speed_pwm_offset = 0x0,
      .speed_tach_outer_offset = 0x10,
      .speed_tach_inner_offset = 0x20,

      .mask_platform = GENMASK(1, 0),
      .mask_id = GENMASK(4, 0),
      .mask_pwm = GENMASK(7, 0),
      .mask_tach = GENMASK(15, 0),
      .mask_green_led = 1,
      .mask_red_led = 2
   },
};

/* Constants */
#define FAN_LED_COLOR_GREEN(_fan) \
    (0xff & (_fan)->fan_group->platform->mask_green_led)
#define FAN_LED_COLOR_RED(_fan) \
    (0xff & (_fan)->fan_group->platform->mask_green_red)

/* Helpers to calculate register address */
#define FAN_ADDR(_group, _type) \
    ((_group)->addr_base + (_group)->platform->_type##_offset)
#define FAN_ADDR_2(_group, _type, _index) \
    (FAN_ADDR(_group, _type) + (_group)->platform->_type##_step * (_index))
#define FAN_ADDR_3(_group, _type, _index, _type2) \
    (FAN_ADDR_2(_group, _type, _index) + \
     (_group)->platform->_type##_##_type2##_offset)

static const struct fan_platform *fan_platform_find(u32 id) {
   size_t i;

   for (i = 0; i < ARRAY_SIZE(fan_platforms); ++i) {
      if (fan_platforms[i].id == id) {
         return &fan_platforms[i];
      }
   }
   return NULL;
}

static const struct fan_info *fan_info_find(const struct fan_info * infos,
                                            size_t num, u32 fan_id) {
   size_t i;

   for (i = 0; i < num; ++i) {
      if (infos[i].id == fan_id) {
         return &infos[i];
      }
   }
   return NULL;
}

#endif /* !_LINUX_DRIVER_SCD_FAN_H_ */
