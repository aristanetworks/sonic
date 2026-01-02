
MKDIR ?= mkdir
CP ?= cp

# Cross-compilation support: use architecture-specific tools
CROSS_COMPILE ?=
CC ?= $(CROSS_COMPILE)gcc
STRIP ?= $(CROSS_COMPILE)strip

CFLAGS = -fPIC -std=c99 -Wall -Werror -Wextra
#CFLAGS += -DDEBUG -g3
LDFLAGS = -shared

TARGET = libsfp-eeprom.so

all: $(TARGET)

sfp-eeprom.inc: sfp-eeprom-info-c-gen.py
	./sfp-eeprom-info-c-gen.py $@

sfp-eeprom.c: sfp-eeprom.inc sfp-eeprom.h

sfp-eeprom.o: sfp-eeprom.c

$(TARGET): sfp-eeprom.o
	$(CC) $(LDFLAGS) -o $@ $^
	$(STRIP) $@

install::
	$(MKDIR) -p $(DESTDIR)
	$(CP) $(TARGET) $(DESTDIR)

clean::
	$(RM) $(TARGET) sfp-eeprom.inc *.o
