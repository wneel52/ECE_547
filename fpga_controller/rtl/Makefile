filename = top
pcf_file = ./io.pcf
KEY_W ?= 16

SRCS = top.v \
       uart_baud_tick_gen.v \
       uart_rx.v \
       uart_tx.v \
       auth_uart_bridge.v \
       auth_controller_top.v \
       platform_unlock_fsm.v \
       platform_key_store.v \
       key_activation_compare.v

OUTDIR = out/$(KEY_W)
RPTDIR = rpts/$(KEY_W)

JSON = $(OUTDIR)/$(filename).json
BLIF = $(OUTDIR)/$(filename).blif
ASC  = $(OUTDIR)/$(filename).asc
BIN  = $(OUTDIR)/$(filename).bin

YOSYS_LOG   = $(RPTDIR)/yosys.log
NEXTPNR_LOG = $(RPTDIR)/nextpnr.log

ICELINK_DIR=$(shell df | grep iCELink | awk '{print $$6}')

${warning iCELink path: $(ICELINK_DIR)}
${warning KEY_W=$(KEY_W)}

.PHONY: all build prog_flash clean clean_all dirs

all: build

dirs:
	mkdir -p $(OUTDIR) $(RPTDIR)

build: dirs
	yosys -p "read_verilog -sv $(SRCS); hierarchy -top $(filename) -chparam KEY_W $(KEY_W); synth_ice40 -top $(filename) -json $(JSON) -blif $(BLIF)" 2>&1 | tee $(YOSYS_LOG)
	nextpnr-ice40 --lp1k --package cm36 --json $(JSON) --pcf $(pcf_file) --asc $(ASC) --freq 48 2>&1 | tee $(NEXTPNR_LOG)
	icepack $(ASC) $(BIN)

prog_flash: build
	@if [ -d '$(ICELINK_DIR)' ]; then \
		cp $(BIN) $(ICELINK_DIR); \
	else \
		echo "iCELink not found"; \
		exit 1; \
	fi

clean:
	rm -rf $(OUTDIR) $(RPTDIR)

clean_all:
	rm -rf out rpts
