# Included after upstream Makefile. Only fftools objects get the adapter hooks.
$(OBJS-ffmpeg): CFLAGS += -fvisibility=hidden -include $(HMOS_COMMAND_DIR)/hooks.h
hmos-command-entry.o: $(HMOS_COMMAND_DIR)/entry.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -fvisibility=hidden -I$(HMOS_COMMAND_DIR) -c $< -o $@
# HMOS_COMMAND_LIBS permits a local experiment against a verified published SDK.
HMOS_COMMAND_DEPS = $(if $(HMOS_COMMAND_LIBS),,$(FF_DEP_LIBS))
libhmosffmpegcmd.so: $(OBJS-ffmpeg) hmos-command-entry.o $(HMOS_COMMAND_DEPS)
	$(LD) $(LDFLAGS) -shared -Wl,-z,defs -Wl,-Bsymbolic -Wl,--exclude-libs,ALL -Wl,-soname,libhmosffmpegcmd.so -o $@ $(OBJS-ffmpeg) hmos-command-entry.o $(if $(HMOS_COMMAND_LIBS),$(HMOS_COMMAND_LIBS),$(FF_EXTRALIBS) $(EXTRALIBS-ffmpeg))
