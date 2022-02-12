#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <math.h>

// How to send inputs over eth

// Build like:
// g++ pixels_to_eth.c -I ~/pipelinec_output -o pixels_to_eth

// 'Software' side of ethernet
#include "../eth/eth_sw.c"

#include "pixels_update.h"
#include "type_bytes_t.h/pixels_update_t_bytes_t.h/pixels_update_t_bytes.h" // Autogenerated
void write_update(pixels_update_t* input)
{
 // Copy into buffer
 uint8_t buffer[pixels_update_t_SIZE];
 pixels_update_t_to_bytes(input, buffer);
 // Send buffer
 eth_write(buffer, pixels_update_t_SIZE);  
}

int main(int argc, char *argv[])
{
    // Open stdin for reading pixels from video_to_pixels.py
    FILE* stdin_file = freopen(NULL, "rb", stdin);
    
    // Init msgs to/from FPGA
    init_eth();
    
    printf("Reading pixels, sending pixels...\n");
    pixels_update_t update;
    while(1)
    {
        // Read pixels update from python
        if( fread(&update, sizeof(pixels_update_t), 1, stdin_file) < 1 )
        {
            printf("No more updates...\n");
            break;
        }
        // Write pixels to FPGA
        write_update(&update);
        usleep(1); // Temp for no overflow
    }
    fclose(stdin_file);

    // Close eth to/from FPGA
	  close_eth();

    return 0;
}
