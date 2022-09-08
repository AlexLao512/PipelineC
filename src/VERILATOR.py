import os
import shutil
import sys

import C_TO_LOGIC
import OPEN_TOOLS
import SIM
import SYN
import VHDL
from utilities import GET_TOOL_PATH, REPO_ABS_DIR

VERILATOR_EXE = "verilator"
VERILATOR_BIN_PATH = OPEN_TOOLS.OSS_CAD_SUITE_PATH + "/bin"

if not os.path.exists(VERILATOR_BIN_PATH):
    VERILATOR_EXE_PATH = GET_TOOL_PATH(VERILATOR_EXE)
    if VERILATOR_EXE_PATH is not None:
        VERILATOR_BIN_PATH = os.path.abspath(os.path.dirname(VERILATOR_EXE_PATH))


def DO_SIM(multimain_timing_params, parser_state, args):
    print(
        "================== Doing Verilator Simulation ================================",
        flush=True,
    )
    VERILATOR_OUT_DIR = SYN.SYN_OUTPUT_DIRECTORY + "/verilator"
    if not os.path.exists(VERILATOR_OUT_DIR):
        os.makedirs(VERILATOR_OUT_DIR)
    # Generate helpful include of verilator names
    names_text = ""
    # Clocks
    clock_name_to_mhz, out_filepath = SYN.GET_CLK_TO_MHZ_AND_CONSTRAINTS_PATH(
        parser_state, None, True
    )
    # Which ones are not from the user internal
    clock_port_is_clk = True
    for clk_mhz in parser_state.clk_mhz.values():
        clk_name = "clk_" + VHDL.CLK_MHZ_GROUP_TEXT(clk_mhz, None)
        # Remove user clocks from dict
        clock_name_to_mhz.pop(clk_name, None)
    if len(clock_name_to_mhz) > 1:
        clock_port_is_clk = False
        for clock_name, mhz in clock_name_to_mhz.items():
            if mhz:
                names_text += f'#define {clock_name} {clock_name.replace("__","_")}\n'
            else:
                names_text += f'#define clk {clock_name.replace("__","_")}\n'
    elif len(clock_name_to_mhz) == 1:
        clock_name, mhz = list(clock_name_to_mhz.items())[0]
        names_text += f'#define clk {clock_name.replace("__","_")}\n'
    else:
        # All clocks are not auto generated, no idea what input ports are clocks?
        # Probably user clocks with user known constant names handled by user
        # Issue warning?
        clock_port_is_clk = False

    # Debug ports
    debug_names = []
    for func in parser_state.main_mhz:
        debug_name = func.split("_DEBUG")[0]
        if func.endswith("_DEBUG_OUTPUT_MAIN"):
            debug_names.append(debug_name)
            debug_verilator_name = func.replace("__", "_") + "_return_output"
            names_text += f"#define {debug_name} {debug_verilator_name}\n"
        if func.endswith("_DEBUG_INPUT_MAIN"):
            debug_names.append(debug_name)
            debug_verilator_name = func.replace("__", "_") + "_val"
            names_text += f"#define {debug_name} {debug_verilator_name}\n"
    names_text += """#define DUMP_PIPELINEC_DEBUG(top) \
cout <<"""
    for debug_name in debug_names:
        names_text += (
            '"'
            + debug_name
            + ': " << to_string('
            + "top->"
            + debug_name
            + ") << "
            + '" " << '
        )
    names_text += "endl;\n"

    # Main func latencies
    for func in parser_state.main_mhz:
        if multimain_timing_params is not None:
            main_timing_params = multimain_timing_params.TimingParamsLookupTable[func]
            main_latency = main_timing_params.GET_TOTAL_LATENCY(
                parser_state, multimain_timing_params.TimingParamsLookupTable
            )
        else:
            main_latency = 0
        names_text += f"#define {func}_LATENCY {main_latency}\n"

    # Write names files
    names_h_path = VERILATOR_OUT_DIR + "/pipelinec_verilator.h"
    f = open(names_h_path, "w")
    f.write(names_text)
    f.close()

    # Generate main.cpp
    main_cpp_text = """
// Default main.cpp template

// Names and helper macro generated by PipelineC tool
#include "pipelinec_verilator.h"

// Generated by Verilator
#include "verilated.h"
#include "Vtop.h" 

#include <iostream>
using namespace std;

int main(int argc, char *argv[]) {
    Vtop* g_top = new Vtop;
    
    // Run the simulation for 10 cycles\n"""
    # Comment out sim cycles if clock is not known
    if not clock_port_is_clk:
        main_cpp_text += """    /* User needs to specify how to drive clock(s)\n"""
    main_cpp_text += """    uint64_t cycle = 0;
    while (cycle < 10)
    {
        // Print the PipelineC debug vars
        cout << "cycle " << cycle << ": ";
        DUMP_PIPELINEC_DEBUG(g_top)

        g_top->clk = 0;
        g_top->eval();

        g_top->clk = 1;
        g_top->eval();
        ++cycle;
    }\n"""
    if not clock_port_is_clk:
        main_cpp_text += """    */\n"""
    main_cpp_text += """  return 0;
}
"""
    main_cpp_path = VERILATOR_OUT_DIR + "/" + "main.cpp"
    f = open(main_cpp_path, "w")
    f.write(main_cpp_text)
    f.close()

    # Use main cpp template or not?
    if args.main_cpp is not None:
        main_cpp_path = os.path.abspath(args.main_cpp)

    # Generate+compile sim .cpp from output VHDL
    # Get all vhd files in syn output
    vhd_files = SIM.GET_SIM_FILES(latency=0)

    # Identify tool versions
    if os.path.exists(f"{OPEN_TOOLS.GHDL_BIN_PATH}/ghdl"):
        print(
            OPEN_TOOLS.GHDL_BIN_PATH
            + "\n"
            + C_TO_LOGIC.GET_SHELL_CMD_OUTPUT(
                f"{OPEN_TOOLS.GHDL_BIN_PATH}/ghdl --version"
            ),
            flush=True,
        )
    else:
        raise Exception("ghdl executable not found!")
    if os.path.exists(f"{OPEN_TOOLS.YOSYS_BIN_PATH}/yosys"):
        print(
            OPEN_TOOLS.YOSYS_BIN_PATH
            + "\n"
            + C_TO_LOGIC.GET_SHELL_CMD_OUTPUT(
                f"{OPEN_TOOLS.YOSYS_BIN_PATH}/yosys --version"
            ),
            flush=True,
        )
    else:
        raise Exception("yosys executable not found!")
    if os.path.exists(f"{VERILATOR_BIN_PATH}/verilator"):
        print(
            VERILATOR_BIN_PATH
            + "\n"
            + C_TO_LOGIC.GET_SHELL_CMD_OUTPUT(
                f"{VERILATOR_BIN_PATH}/verilator --version"
            ),
            flush=True,
        )
    else:
        raise Exception("verilator executable not found!")

    # Write a shell script to execute
    m_ghdl = ""
    if not OPEN_TOOLS.GHDL_PLUGIN_BUILT_IN:
        m_ghdl = "-m ghdl "
    sh_text = f"""
{OPEN_TOOLS.GHDL_BIN_PATH}/ghdl -i --std=08 `cat ../vhdl_files.txt` && \
{OPEN_TOOLS.GHDL_BIN_PATH}/ghdl -m --std=08 top && \
{OPEN_TOOLS.YOSYS_BIN_PATH}/yosys -g {m_ghdl} -p "ghdl --std=08 top; proc; opt; fsm; opt; memory; opt; write_verilog ../top/top.v" && \
{VERILATOR_BIN_PATH}/verilator -Wno-UNOPTFLAT -Wno-WIDTH -Wno-CASEOVERLAP --top-module top -cc ../top/top.v -O3 --exe {main_cpp_path} -I{VERILATOR_OUT_DIR} -I{REPO_ABS_DIR()} && \
make CXXFLAGS="-I{VERILATOR_OUT_DIR} -I{REPO_ABS_DIR()}" -j4 -C obj_dir -f Vtop.mk
"""
    # --report-unoptflat
    sh_path = VERILATOR_OUT_DIR + "/" + "verilator.sh"
    f = open(sh_path, "w")
    f.write(sh_text)
    f.close()

    # Run compile
    print(f"Compiling PipelineC VHDL output + {main_cpp_path}...", flush=True)
    bash_cmd = f"bash {sh_path}"
    # print(bash_cmd, flush=True)
    log_text = C_TO_LOGIC.GET_SHELL_CMD_OUTPUT(bash_cmd, cwd=VERILATOR_OUT_DIR)
    # print(log_text, flush=True)

    # Run the simulation
    print("Starting simulation...", flush=True)
    bash_cmd = "./obj_dir/Vtop"
    # print(bash_cmd, flush=True)
    log_text = C_TO_LOGIC.GET_SHELL_CMD_OUTPUT(bash_cmd, cwd=VERILATOR_OUT_DIR)
    print(log_text, flush=True)
    sys.exit(0)
