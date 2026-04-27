module key_activation_compare #(
    parameter int SIZE = 32
)(
    input logic [SIZE-1:0] key_in, // input written to key buffer from CPU
    input logic [SIZE-1:0] key_hw, // key in use
    output logic match
);
    logic [SIZE-1:0] diff;
    // compare full vector -> no early exists causing comprimised security
    assign diff = key_in ^ key_hw; // input key XOR hw key
    assign match = ~(|diff);
endmodule
