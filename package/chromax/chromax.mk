CHROMAX_VERSION = 0.1.0
CHROMAX_SITE = $(BR2_EXTERNAL_CHROMAX_PATH)/src
CHROMAX_SITE_METHOD = local
CHROMAX_LICENSE = MIT
CHROMAX_LICENSE_FILES = LICENSE
CHROMAX_DEPENDENCIES = python3

define CHROMAX_INSTALL_TARGET_CMDS
	mkdir -p $(TARGET_DIR)/usr/lib/chromax $(TARGET_DIR)/usr/bin
	cp -a $(@D)/chromax $(TARGET_DIR)/usr/lib/chromax/
	$(INSTALL) -m 0755 $(@D)/chromaxctl $(TARGET_DIR)/usr/bin/chromaxctl
	ln -sf chromaxctl $(TARGET_DIR)/usr/bin/ai
endef

$(eval $(generic-package))
