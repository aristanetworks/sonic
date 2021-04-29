// Copyright (c) 2021 Arista Networks, Inc.  All rights reserved.

#ifndef SFP_EEPROM_API_H_
#define SFP_EEPROM_API_H_

#include <stdint.h>
#include <sys/types.h>

typedef uint16_t phyid_t;

ssize_t read_eeprom(
   phyid_t  phy_id, /**< physical port ID > **/
   uint16_t offset, /** same format offset as in SONIC Y-Cable read_eeprom */
   uint8_t  *value,  /**< pointer to a byte array, size is same as len value. */
   uint8_t  len    /** number of bytes */
   );

ssize_t write_eeprom(
   phyid_t  phy_id, /**< physical port ID > **/
   uint16_t offset, /** same format offset as in SONIC Y-Cable read_eeprom */
   const uint8_t *value,  /**< pointer to a byte array, size is same as len value. */
   uint8_t  len    /** number of bytes */
   );

#endif // SFP_EEPROM_API_H_
