module platform_unlock_fsm(
    input logic clk,
    input logic reset,

    input logic zeroize_in, // external zeroize
    input logic do_compare, // pulse from commit buffer
    input logic match_q, // compare latch from buffer
    input logic commit_illegal, // partial or illegal commit

    output logic aes_enable,
    output logic unlocked,
    output logic auth_zeroize, // request to clear cicruit
    output logic [1:0] key_sel, // which platform key do we want to compare
    output logic [1:0] state_debug

);

    typedef enum logic [1:0] {
        WAIT_K0 = 2'd0,
        WAIT_K1 = 2'd1,
        WAIT_K2 = 2'd2,
        UNLOCKED = 2'd3
    } state_t;

    state_t state, next_state;

    always_ff @(posedge clk) begin
        if (reset)
            state <= WAIT_K0;
        else
            state <= next_state;
    end

    // comb behavior -> handles different input cases
    always_comb begin
        next_state = state;
        auth_zeroize = 1'b0;
        aes_enable = 1'b0;
        unlocked = 1'b0;
        key_sel = 2'd0;
        state_debug = state;

        case (state)
            WAIT_K0: begin
                key_sel = 2'd0;
                if (zeroize_in) begin // handle zeroize
                    auth_zeroize = 1'b1;
                    next_state = WAIT_K0;
                end
                else if (commit_illegal) begin
                    auth_zeroize = 1'b1;
                    next_state = WAIT_K0;
                end
                else if (do_compare) begin
                    if (match_q) begin
                        next_state = WAIT_K1;
                    end
                    else begin
                        auth_zeroize = 1'b1;
                        next_state = WAIT_K0;
                    end
                end
            end
            WAIT_K1: begin
                key_sel = 2'd1;
                if (zeroize_in) begin
                    auth_zeroize = 1'b1;
                    next_state = WAIT_K0;
                end
                else if (commit_illegal) begin
                    auth_zeroize = 1'b1;
                    next_state = WAIT_K0;
                end
                else if (do_compare) begin
                    if (match_q) begin
                        next_state = WAIT_K2;
                    end
                    else begin
                        auth_zeroize = 1'b1;
                        next_state = WAIT_K0;
                    end
                end
            end
            WAIT_K2: begin
                key_sel = 2'd2;
                if (zeroize_in) begin
                    auth_zeroize = 1'b1;
                    next_state = WAIT_K0;
                end
                else if (commit_illegal) begin
                    auth_zeroize = 1'b1;
                    next_state = WAIT_K0;
                end
                else if (do_compare) begin
                    if (match_q) begin
                        next_state = UNLOCKED;
                    end
                    else begin
                        auth_zeroize = 1'b1;
                        next_state = WAIT_K0;
                    end
                end
            end
            UNLOCKED: begin
                aes_enable = 1'b1;
                unlocked = 1'b1;
                key_sel = 2'd0;
                if (zeroize_in) begin
                    auth_zeroize = 1'b1;
                    next_state = WAIT_K0;
                end
            end
            default: begin
                auth_zeroize = 1'b1;
                next_state = WAIT_K0;
            end
        endcase

    end

endmodule
