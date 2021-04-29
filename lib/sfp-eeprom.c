// Copyright (c) 2021 Arista Networks, Inc.  All rights reserved.

#define _GNU_SOURCE
#define VERSION 1.0

#include <assert.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "sfp-eeprom.h"

#ifdef DEBUG
# define DBG(...) fprintf(stderr, ##__VA_ARGS__)
#else
# define DBG(...)
#endif

#define DBGF(_fmt, ...) DBG(__func__ _fmt, ##__VA_ARGS__)

#define CMDLINE_SZ 4096
#define ADAPTER_NAME_SZ 64
#define BUS_INVALID ((uint32_t)-1)
#define NUM_BUS_MAX 256
#define ADAPTER_PATH "/sys/class/i2c-adapter"

struct xcvr_info {
   uint16_t id;
   uint16_t addr;
   char bus[ADAPTER_NAME_SZ];
};

struct platform_info {
   const char *name;
   const struct xcvr_info *xcvrs;
   const int ports;
};

struct phy_info {
   phyid_t phy_id;
   int bus;    // i2c bus number
   int addr;   // addr of device
   int eeprom; // optoe eeprom fd
};

struct context {
   bool initialized;
   const struct platform_info *platform;
   struct phy_info *phys;
};

struct i2c_bus {
   char name[ADAPTER_NAME_SZ];
   uint32_t id;
};

#define ARRAY_SIZE(_array) (sizeof(_array) / sizeof(*_array))

#pragma GCC diagnostic ignored "-Woverride-init"
#define SFP(...) (struct xcvr_info){ .addr = 0x50, ##__VA_ARGS__ }
#define QSFP(...) (struct xcvr_info){ .addr = 0x50, ##__VA_ARGS__ }
#define OSFP(...) (struct xcvr_info){ .addr = 0x50, ##__VA_ARGS__ }
#define PLATFORM(_name, _xcvrs) { \
   .name = _name, \
   .xcvrs = _xcvrs, \
   .ports = ARRAY_SIZE(_xcvrs), \
}

#include "sfp-eeprom.inc"
#pragma GCC diagnostic error "-Woverride-init"

static char *get_proc_cmdline_value(const char *key) {
   char buffer[CMDLINE_SZ + 1] = {0};
   int fd;
   ssize_t len;
   char *tmp;
   char *begin;

   fd = open("/proc/cmdline", 0);
   len = read(fd, buffer, CMDLINE_SZ);
   close(fd);

   if (len <= 0)
      return NULL;

   tmp = strstr(buffer, key);
   if (!tmp)
      return tmp;

   tmp += strlen(key);
   if (*tmp != '=')
      return NULL;

   tmp += 1;
   begin = tmp;
   for (; *tmp; tmp++)
      if (*tmp == ' ')
         break;

   return strndup(begin, tmp - begin);
}

static const struct platform_info *get_platform() {
   const struct platform_info *platform;
   char *name = secure_getenv("SKU_SID");

   if (!name)
      name = get_proc_cmdline_value("sid");
   else
      name = strdup(name);

   assert(name && "failed to detect platform, you can override with SKU_SID=");

   for (long unsigned int i = 0; i < ARRAY_SIZE(platforms); i++) {
      platform = &platforms[i];
      if (!strncmp(platform->name, name, strlen(platform->name))) {
         free(name);
         return platform;
      }
   }

   free(name);
   return NULL;
}

ssize_t read_adapter_name(const char *name, char *buffer, size_t len) {
   char path[PATH_MAX];
   ssize_t size;
   int fd;

   snprintf(path, PATH_MAX, ADAPTER_PATH "/%s/name", name);

   fd = open(path, O_RDONLY);
   if (fd < 0) {
      DBGF("path name %s does not exist\n", path)
      return fd;
   }

   size = read(fd, buffer, len);
   if (size > 0)
      buffer[size - 1] = '\0';

   close(fd);
   return size;
}

static struct i2c_bus *load_i2c_adapters() {
   DIR *dp;
   struct dirent *ep;
   struct i2c_bus *bus;
   struct i2c_bus *buses = calloc(NUM_BUS_MAX, sizeof(struct i2c_bus));
   uint32_t idx = 0;

   if (!buses)
      return NULL;

   dp = opendir(ADAPTER_PATH);
   assert(dp && "failed to list available i2c-adapters");

   while ((ep = readdir (dp)) && idx < NUM_BUS_MAX - 1) {
      if (strncmp(ep->d_name, "i2c-", 4)) {
         DBGF("unexpected bus name %s\n", ep->d_name);
         continue;
      }
      bus = &buses[idx];
      if (!read_adapter_name(ep->d_name, bus->name, sizeof(bus->name))) {
         DBGF("failed to read adapter name for %s\n", ep->d_name);
         continue;
      }
      bus->id = atoi(ep->d_name + 4);
      idx++;
   }

   bus->id = BUS_INVALID;

   return buses;
}

static uint32_t get_bus_for_xcvr(const struct i2c_bus *adapters,
                                 const struct xcvr_info *xcvr) {
   const struct i2c_bus *bus;
   for (uint32_t i = 0; adapters[i].id != BUS_INVALID; i++) {
      bus = &adapters[i];
      if (!strcmp(bus->name, xcvr->bus))
         return bus->id;
   }

   return BUS_INVALID;
}

static int init_runtime_context(struct context *ctx) {
   assert(!ctx->initialized);

   ctx->platform = get_platform();
   assert(ctx->platform && "failed to identify platform");

   DBG("sfp_eeprom: initializing library for platform %s\n", ctx->platform->name);

   ctx->phys = calloc(ctx->platform->ports, sizeof(struct phy_info));
   assert(ctx->phys && "failed to allocate phy_info");

   struct i2c_bus *buses = load_i2c_adapters();
   assert(buses && "failed to load i2c adapter bus names");

   struct phy_info *info;
   const struct xcvr_info *xcvr;
   for (int i = 0; i < ctx->platform->ports; i++) {
      xcvr = &ctx->platform->xcvrs[i];
      assert(xcvr->id > 0 && xcvr->id <= ctx->platform->ports);
      info = &ctx->phys[xcvr->id - 1];
      info->phy_id = xcvr->id;
      info->addr = xcvr->addr;
      info->bus = get_bus_for_xcvr(buses, xcvr);
      info->eeprom = -1;
   }

   free(buses);

   ctx->initialized = true;
   return 0;
}

static struct context *get_runtime_context() {
   static struct context ctx;
   if (!ctx.initialized)
      init_runtime_context(&ctx);
   return &ctx;
}

static int open_eeprom_fd(struct phy_info *info) {
   int fd;
   char eeprom_path[PATH_MAX];

   snprintf(eeprom_path, sizeof(eeprom_path),
            "/sys/bus/i2c/devices/%d-%04x/eeprom",
            info->bus, info->addr);

   fd = open(eeprom_path, O_RDWR | O_CLOEXEC | O_SYNC);
   if (fd < 0) {
      DBG("open_eeprom_fd(%u): errno=%d: failed to open path %s\n",
          info->phy_id, errno, eeprom_path);
      return fd;
   }

   return fd;
}

static struct phy_info *get_phy_info(phyid_t phy_id) {
   struct context *ctx = get_runtime_context();
   assert(phy_id > 0 && phy_id <= ctx->platform->ports && "Invalid phy_id parameter");
   return &ctx->phys[phy_id - 1];
}

int get_phy_eeprom_fd(phyid_t phy_id) {
   struct phy_info *info = get_phy_info(phy_id);
   if (info->eeprom < 0) {
      info->eeprom = open_eeprom_fd(info);
   }
   return info->eeprom;
}

ssize_t read_eeprom(uint16_t phy_id, uint16_t offset, uint8_t *value, uint8_t len)
{
   off_t ret;
   int fd = get_phy_eeprom_fd(phy_id);

   ret = lseek(fd, offset, SEEK_SET);
   if (ret == -1) {
      DBG("read_eeprom(%u): errno=%d: failed to seek to offset %d\n",
          phy_id, errno, offset);
      return -1;
   }

   return read(fd, value, len);
}

ssize_t write_eeprom(uint16_t phy_id, uint16_t offset, const uint8_t *value, uint8_t len)
{
   off_t ret;
   int fd = get_phy_eeprom_fd(phy_id);

   ret = lseek(fd, offset, SEEK_SET);
   if (ret == -1) {
      DBG("write_eeprom(%u): errno=%d: failed to seek to offset %d\n",
          phy_id, errno, offset);
      return -1;
   }

   return write(fd, value, len);
}
