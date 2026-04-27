module auth_controller_top #(
    parameter int KEY_W = 32
)(
    input logic              clk,
    input logic              reset,
    input logic              zeroize_in,
    input logic              tamper_in,
    input logic              do_compare,
    input logic              commit_illegal,
    input logic [KEY_W-1:0]  auth_key_in,

    output logic              aes_enable,
    output logic              unlocked,
    output logic              auth_zeroize,
    output logic              tamper_latched,
    output logic [1:0]        key_sel,
    output logic [1:0]        state_debug
);

    logic [KEY_W-1:0] key_hw;
    logic             match_q;

    // sync tamper with clk
    logic sync_tamper0, sync_tamper1;

    // arm trap counter
    logic [15:0] tamper_arm_count;
    logic trap_armed;

    logic aes_enable_fsm;
    logic unlocked_fsm;
    logic auth_zeroize_fsm;

    platform_key_store #(
        .KEY_W(KEY_W)
    ) unit_key_store (
        .key_sel(key_sel),
        .key_out(key_hw)
    );

    key_activation_compare #(
        .SIZE(KEY_W)
    ) unit_compare (
        .key_in(auth_key_in),
        .key_hw(key_hw),
        .match(match_q)
    );

    platform_unlock_fsm unit_fsm (
        .clk(clk),
        .reset(reset),
        .zeroize_in(zeroize_in),
        .do_compare(do_compare),
        .match_q(match_q),
        .commit_illegal(commit_illegal),
        .aes_enable(aes_enable_fsm),
        .unlocked(unlocked_fsm),
        .auth_zeroize(auth_zeroize_fsm),
        .key_sel(key_sel),
        .state_debug(state_debug)
    );

    // synch tamper
    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            sync_tamper0 <= 1'b1;
            sync_tamper1 <= 1'b1;
            tamper_latched <= 1'b0;
            trap_armed <= 1'b0;
            tamper_arm_count <= 16'd0;
        end
        else begin
            // align tamper signal with clk
            sync_tamper0 <= tamper_in;
            sync_tamper1 <= sync_tamper0;
            
            // armming delay on startup
            if(!trap_armed) begin
                tamper_arm_count <= tamper_arm_count + 1;
                if (tamper_arm_count == 16'hFFFF) begin
                    trap_armed <= 1'b1;
                end
            end
            
            // active low tamper (bitline active = not-tampered)
            if(trap_armed && !sync_tamper1) begin
                tamper_latched <= 1'b1;
            end
        end
    end


    // tamper override
    assign unlocked     = tamper_latched ? 1'b0 : unlocked_fsm;
    assign aes_enable   = tamper_latched ? 1'b0 : aes_enable_fsm;
    assign auth_zeroize = tamper_latched ? 1'b1 : auth_zeroize_fsm; 

endmodule
 
