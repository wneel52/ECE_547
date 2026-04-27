module top #(
   parameter int KEY_W = 16
)(
    input  logic CLK,
    input  logic RX,
    input  logic TAMPER_IN,
    output logic TX,
    output logic LED0,
    output logic LED1,
    output logic LED2,
    output logic LED3,
    output logic LED4,
    output logic LED5
);

    // reset on startup
    logic reset = 1'b1;
    logic [7:0]  rst_count = 8'd0;
    logic [23:0] hb_count  = 24'd0;

    // UART wires
    logic [7:0] rx_data;
    logic       rx_valid;
    logic       rx_idle;
    logic       rx_eop;

    logic [7:0] tx_data;
    logic       tx_start;
    logic       tx_busy;

    // bridge <-> controller wires
    logic        zeroize_in;
    logic        do_compare;
    logic        commit_illegal;
    logic [KEY_W-1:0] auth_key_in;

    logic        aes_enable;
    logic        unlocked;
    logic        auth_zeroize;
    logic        tamper_latched;
    logic [1:0]  key_sel;
    logic [1:0]  state_debug;

    // power-on reset + heartbeat
    always_ff @(posedge CLK) begin
        if (rst_count < 8'hFF) begin
            rst_count <= rst_count + 1'b1;
            reset     <= 1'b1;
        end else begin
            reset     <= 1'b0;
        end

        hb_count <= hb_count + 1'b1;
    end

    // UART RX
    uart_rx #(
        .clk_freq(12000000),
        .baud(115200)
    ) unit_uart_rx (
        .clk(CLK),
        .rx(RX),
        .rx_ready(rx_valid),
        .rx_data(rx_data),
        .rx_idle(rx_idle),
        .rx_eop(rx_eop)
    );

    // UART TX
    uart_tx #(
        .clk_freq(12000000),
        .baud(115200)
    ) unit_uart_tx (
        .clk(CLK),
        .tx_start(tx_start),
        .tx_data(tx_data),
        .tx(TX),
        .tx_busy(tx_busy)
    );

    // UART command bridge
    auth_uart_bridge #(
        .KEY_W(KEY_W)
    ) unit_bridge (
        .clk(CLK),
        .reset(reset),
        .rx_data(rx_data),
        .rx_valid(rx_valid),
        .tx_data(tx_data),
        .tx_start(tx_start),
        .tx_busy(tx_busy),
        .zeroize_in(zeroize_in),
        .do_compare(do_compare),
        .commit_illegal(commit_illegal),
        .auth_key_in(auth_key_in),
        .aes_enable(aes_enable),
        .unlocked(unlocked),
        .auth_zeroize(auth_zeroize),
        .key_sel(key_sel),
        .state_debug(state_debug)
    );

    // auth controller 
    auth_controller_top #(
        .KEY_W(KEY_W)
    ) unit_controller (
        .clk(CLK),
        .reset(reset),
        .zeroize_in(zeroize_in),
        .tamper_in(TAMPER_IN),
        .do_compare(do_compare),
        .commit_illegal(commit_illegal),
        .auth_key_in(auth_key_in),
        .aes_enable(aes_enable),
        .unlocked(unlocked),
        .auth_zeroize(auth_zeroize),
        .tamper_latched(tamper_latched),
        .key_sel(key_sel),
        .state_debug(state_debug)
    );

    // LEDs
    assign LED0 = hb_count[23];
    assign LED1 = state_debug[1];
    assign LED2 = state_debug[0];
    assign LED3 = aes_enable;
    assign LED4 = unlocked;
    assign LED5 = tamper_latched;

endmodule
