module platform_key_store #(
    parameter int KEY_W = 32
)(
    input logic [1:0] key_sel,
    output logic [KEY_W-1:0] key_out
);

    // cast w/ w width to isolate keybits
    localparam logic [KEY_W-1:0] PK0 = KEY_W'(128'h00112233_44556677_8899AABB_CCDDEEFF);
    localparam logic [KEY_W-1:0] PK1 = KEY_W'(128'h11111111_22222222_33333333_44444444);
    localparam logic [KEY_W-1:0] PK2 = KEY_W'(128'hAAAABBBB_CCCCDDDD_EEEEFFFF_12345678);

    always_comb begin
        case (key_sel)
            2'd0: key_out = PK0;
            2'd1: key_out = PK1;
            2'd2: key_out = PK2;
            default: key_out = '0;
        endcase
    end

endmodule
