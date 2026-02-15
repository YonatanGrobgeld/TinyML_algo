#!/usr/bin/env python3
"""
Enhanced FPGA Baseline Measurement Script with Comprehensive UART Debugging

This script runs the baseline TinyML algorithm on an FPGA via UART and measures
execution time. It includes extensive debugging features to diagnose communication issues.
"""
import serial
import serial.tools.list_ports
import time
import sys
import csv
import argparse
from pathlib import Path


def find_serial_port():
    """Auto-detect USB-UART devices"""
    ports = list(serial.tools.list_ports.comports())
    candidates = []
    for p in ports:
        if "USB" in p.device or "ACM" in p.device:
            candidates.append(p.device)
    
    if not candidates:
        return None
    
    # Prefer ttyUSB1 if available (often the UART interface on Digilent boards)
    candidates.sort()
    for c in candidates:
        if "ttyUSB1" in c:
            return c
            
    return candidates[0]


def bytes_to_hex(data):
    """Convert bytes to hex string for debugging"""
    return ' '.join(f'{b:02X}' for b in data)


def capture_boot_messages(ser, timeout_s=2.0, debug_log=None, verbose=False):
    """
    Capture any boot/banner messages from the FPGA.
    Returns list of lines received.
    """
    print(f"\n--- Capturing boot messages ({timeout_s}s) ---")
    ser.reset_input_buffer()
    
    lines = []
    end_time = time.time() + timeout_s
    
    while time.time() < end_time:
        remaining = end_time - time.time()
        if remaining <= 0:
            break
            
        # Use short timeout for responsive reading
        ser.timeout = min(0.5, remaining)
        try:
            line = ser.readline()
            if line:
                try:
                    decoded = line.decode('utf-8', errors='replace').strip()
                    if decoded:
                        lines.append(decoded)
                        if verbose:
                            print(f"  BOOT: {decoded}")
                        if debug_log:
                            debug_log.write(f"BOOT: {decoded}\n")
                            debug_log.flush()
                except:
                    # Binary data - show hex
                    hex_str = bytes_to_hex(line)
                    lines.append(f"[HEX: {hex_str}]")
                    if verbose:
                        print(f"  BOOT [HEX]: {hex_str}")
                    if debug_log:
                        debug_log.write(f"BOOT [HEX]: {hex_str}\n")
                        debug_log.flush()
        except Exception as e:
            break
    
    if lines:
        print(f"Received {len(lines)} boot message(s)")
    else:
        print("⚠ WARNING: No boot messages received!")
        print("  This suggests:")
        print("    - FPGA firmware is not running")
        print("    - Wrong COM port")
        print("    - Wrong baud rate")
        print("    - FPGA in bootloader mode")
    
    return lines


def main():
    parser = argparse.ArgumentParser(
        description='Run baseline on FPGA and measure time with enhanced debugging.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic run
  %(prog)s --port COM3 --runs 10 --power_val estimate
  
  # With full debugging
  %(prog)s --port COM3 --runs 10 --power_val estimate --verbose --log_hex
  
  # Different serial settings
  %(prog)s --port COM3 --baud 9600 --timeout_s 60 --runs 5
        """
    )
    
    # Port settings
    parser.add_argument('--port', help='Serial port device (e.g., COM3, /dev/ttyUSB1)')
    parser.add_argument('--baud', type=int, default=115200, help='Baud rate (default: 115200)')
    parser.add_argument('--timeout_s', type=float, default=30.0, help='Timeout per run in seconds (default: 30)')
    parser.add_argument('--bytesize', type=int, default=8, choices=[5,6,7,8], help='Data bits (default: 8)')
    parser.add_argument('--parity', default='N', choices=['N','E','O','M','S'], help='Parity: N=None, E=Even, O=Odd (default: N)')
    parser.add_argument('--stopbits', type=float, default=1, choices=[1, 1.5, 2], help='Stop bits (default: 1)')
    parser.add_argument('--xonxoff', action='store_true', help='Enable software flow control')
    parser.add_argument('--rtscts', action='store_true', help='Enable RTS/CTS hardware flow control')
    parser.add_argument('--dsrdtr', action='store_true', help='Enable DSR/DTR hardware flow control')
    
    # Measurement settings
    parser.add_argument('--runs', type=int, default=10, help='Number of iterations (default: 10)')
    parser.add_argument('--out', default='results_runtime.csv', help='Output CSV file')
    parser.add_argument('--power_val', help='Measured power in Watts (float) or "estimate"', default=None)
    
    # Protocol settings
    parser.add_argument('--done_token', default='Done', help='Success token to wait for (default: "Done")')
    parser.add_argument('--substring_match', action='store_true', help='Use substring matching for done token (more robust)')
    parser.add_argument('--case_insensitive', action='store_true', help='Match done token case-insensitively')
    parser.add_argument('--toggle_dtr', action='store_true', help='Toggle DTR before each run (may reset board)')
    parser.add_argument('--boot_capture_time', type=float, default=2.0, help='Time to capture boot messages (default: 2s)')
    
    # Debugging settings
    parser.add_argument('--debug_log', default='serial_debug.log', help='Debug log file for all serial output')
    parser.add_argument('--log_hex', action='store_true', help='Log raw bytes as hex in debug log')
    parser.add_argument('--verbose', action='store_true', help='Print all serial output to console')
    parser.add_argument('--show_boot', action='store_true', help='Always show boot messages (default: only if --verbose)')
    
    args = parser.parse_args()

    # Auto-detect port if not specified
    port = args.port
    if not port:
        print("Auto-detecting serial port...")
        port = find_serial_port()
        if not port:
            print("Error: No serial port found. Please specify --port.")
            sys.exit(1)
        print(f"Detected port: {port}")

    # Open serial port with explicit settings
    print(f"\n--- Opening Serial Port ---")
    print(f"Port: {port}")
    print(f"Baud: {args.baud}")
    print(f"Format: {args.bytesize}{args.parity}{args.stopbits}")
    print(f"Flow Control: xonxoff={args.xonxoff}, rtscts={args.rtscts}, dsrdtr={args.dsrdtr}")
    print(f"Timeout: {args.timeout_s}s per run")
    
    try:
        ser = serial.Serial(
            port=port,
            baudrate=args.baud,
            bytesize=args.bytesize,
            parity=args.parity,
            stopbits=args.stopbits,
            timeout=args.timeout_s,
            xonxoff=args.xonxoff,
            rtscts=args.rtscts,
            dsrdtr=args.dsrdtr,
            inter_byte_timeout=0.1  # Better readline() behavior
        )
    except Exception as e:
        print(f"Error opening serial port {port}: {e}")
        print("\nTroubleshooting:")
        print("  - Port in use by another program (PuTTY, Vivado, etc.)")
        print("  - Wrong port name (check Device Manager on Windows)")
        print("  - Permission issue (try running as Administrator)")
        sys.exit(1)

    # Open debug log file
    debug_log_path = Path(args.debug_log)
    try:
        debug_log = open(debug_log_path, 'w', encoding='utf-8')
        print(f"Debug log: {debug_log_path.absolute()}")
        debug_log.write(f"=== FPGA Baseline Measurement Debug Log ===\n")
        debug_log.write(f"Port: {port}\n")
        debug_log.write(f"Baud: {args.baud}\n")
        debug_log.write(f"Format: {args.bytesize}{args.parity}{args.stopbits}\n")
        debug_log.write(f"Timeout: {args.timeout_s}s\n")
        debug_log.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        debug_log.write("=" * 60 + "\n\n")
        debug_log.flush()
    except Exception as e:
        print(f"Warning: Could not open debug log {args.debug_log}: {e}")
        debug_log = None

    # Capture boot messages
    boot_lines = capture_boot_messages(
        ser, 
        timeout_s=args.boot_capture_time,
        debug_log=debug_log,
        verbose=(args.verbose or args.show_boot)
    )
    
    if debug_log and boot_lines:
        debug_log.write("\n" + "=" * 60 + "\n")
        debug_log.write("Starting measurement runs...\n")
        debug_log.write("=" * 60 + "\n\n")
        debug_log.flush()

    # Power measurement
    if args.power_val:
        if args.power_val.lower() == "estimate":
             power_val = "Estimate (Vivado report_power)"
        else:
             try:
                 float(args.power_val)
                 power_val = f"{args.power_val} W (Measured)"
             except ValueError:
                 print(f"Warning: Invalid power value '{args.power_val}'. Using Estimate.")
                 power_val = "Estimate (Vivado report_power)"
        print(f"\n--- Power Measurement ---\nUsing: {power_val}")
    else:
        print("\n--- Power Measurement ---")
        print("If you have a USB power meter, enter the measured power in Watts.")
        print("If not available, press Enter to skip (will report 'Estimate').")
        power_str = input("Measured power (W) > ").strip()
        
        power_val = "Estimate (Vivado report_power)"
        if power_str:
            try:
                float(power_str)
                power_val = f"{power_str} W (Measured)"
            except ValueError:
                pass

    print(f"\n--- Starting {args.runs} Measurement Runs ---")
    print(f"Waiting for token: '{args.done_token}'")
    print(f"  Substring match: {args.substring_match}")
    print(f"  Case insensitive: {args.case_insensitive}")

    results = []
    
    # Prepare done token for matching
    done_token = args.done_token
    if args.case_insensitive:
        done_token = done_token.lower()

    for i in range(args.runs):
        print(f"\nRun {i+1}/{args.runs}...", end='', flush=True)
        
        # Flush input buffer
        ser.reset_input_buffer()
        
        # Toggle DTR if requested (may reset some boards)
        if args.toggle_dtr:
            ser.dtr = False
            time.sleep(0.1)
            ser.dtr = True
            time.sleep(0.5)  # Wait for board to boot
        
        # Collect all output for this run
        run_output = []
        raw_bytes_received = bytearray()
        
        # Send start command
        t0 = time.perf_counter()
        ser.write(b's')
        
        if debug_log:
            debug_log.write(f"\n=== Run {i+1}/{args.runs} at {time.strftime('%H:%M:%S')} ===\n")
            debug_log.write("Sent: 's' (0x73)\n")
            if args.log_hex:
                debug_log.write("Sent [HEX]: 73\n")
            debug_log.flush()
        
        # Read until "Done" or timeout
        found_done = False
        line_count = 0
        
        while True:
            line_bytes = ser.readline()
            
            if line_bytes:
                raw_bytes_received.extend(line_bytes)
                line_count += 1
                
                # Try to decode as UTF-8
                try:
                    line = line_bytes.decode('utf-8', errors='replace').strip()
                except:
                    line = "[DECODE ERROR]"
                
                if line:
                    run_output.append(line)
                    
                    if debug_log:
                        debug_log.write(f"{line}\n")
                        if args.log_hex:
                            debug_log.write(f"  [HEX]: {bytes_to_hex(line_bytes)}\n")
                        debug_log.flush()
                    
                    if args.verbose:
                        print(f"\n  RX: {line}", end='', flush=True)
                    
                    # Check for done token
                    check_line = line.lower() if args.case_insensitive else line
                    check_token = done_token.lower() if args.case_insensitive else done_token
                    
                    if args.substring_match:
                        # More robust: check if token appears anywhere in line
                        if check_token in check_line:
                            found_done = True
                            break
                    else:
                        # Exact match
                        if check_line == check_token:
                            found_done = True
                            break
            else:
                # Timeout (no data received)
                if debug_log:
                    debug_log.write(f"[TIMEOUT after {line_count} lines]\n")
                    debug_log.flush()
                break
        
        t1 = time.perf_counter()
        
        if found_done:
            dt = t1 - t0
            results.append(dt)
            print(f" ✓ {dt:.4f}s ({line_count} lines)")
        else:
            print(f" ✗ TIMEOUT/ERROR (no '{args.done_token}')")
            print(f"    Received {line_count} lines, {len(raw_bytes_received)} bytes")
            
            # Show diagnostic info
            if line_count == 0:
                print(f"    ⚠ NO DATA RECEIVED AT ALL")
                print(f"       → Firmware not running, or wrong baud rate")
            elif line_count == 1 and len(run_output) == 1:
                print(f"    Last line: '{run_output[0]}'")
                if run_output[0] == 's':
                    print(f"    ⚠ Only received 's' back - likely:")
                    print(f"       → Firmware not running (FPGA in bootloader or wrong bitstream)")
                    print(f"       → UART loopback/echo enabled")
                    print(f"       → Wrong COM port")
            else:
                print(f"    Last {min(10, len(run_output))} lines:")
                for line in run_output[-10:]:
                    print(f"      {line}")
            
            if debug_log:
                print(f"    📄 Full output logged to: {debug_log_path.absolute()}")
                
                # Log hex dump of last bytes
                if raw_bytes_received:
                    debug_log.write(f"\n[RAW BYTES HEX DUMP - Last {min(100, len(raw_bytes_received))} bytes]:\n")
                    tail = raw_bytes_received[-100:]
                    debug_log.write(bytes_to_hex(tail) + "\n")
                    debug_log.flush()
        
        # Wait before next run
        time.sleep(0.5)

    if debug_log:
        debug_log.write("\n" + "=" * 60 + "\n")
        debug_log.write(f"Measurement complete: {len(results)}/{args.runs} successful\n")
        debug_log.close()

    ser.close()

    if not results:
        print("\n❌ No successful runs.")
        print(f"\n📋 Troubleshooting Checklist:")
        print(f"  1. Check boot messages above - did you see 'MODE: BASELINE' and 'Ready'?")
        print(f"     → If NO: Firmware not running. Reflash FPGA bitstream.")
        print(f"  2. Check debug log: {debug_log_path.absolute()}")
        print(f"  3. Try manual UART test:")
        print(f"     - Open PuTTY/TeraTerm on {port} at {args.baud} baud")
        print(f"     - Reset FPGA (PROG button)")
        print(f"     - Type 's' and press Enter")
        print(f"     - You should see demo output ending with 'Done'")
        print(f"  4. If you see garbage: Try different baud rates (9600, 57600, 115200)")
        sys.exit(1)

    # Calculate statistics
    import statistics
    avg_t = statistics.mean(results)
    min_t = min(results)
    max_t = max(results)
    std_t = statistics.stdev(results) if len(results) > 1 else 0.0

    print("\n" + "=" * 60)
    print("📊 MEASUREMENT SUMMARY")
    print("=" * 60)
    print(f"Successful runs: {len(results)}/{args.runs}")
    print(f"Average time:    {avg_t:.4f} s")
    print(f"Min time:        {min_t:.4f} s")
    print(f"Max time:        {max_t:.4f} s")
    print(f"Std deviation:   {std_t:.4f} s")
    print(f"Power:           {power_val}")
    print("=" * 60)

    # Save CSV
    with open(args.out, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Run", "Time(s)"])
        for idx, val in enumerate(results):
            writer.writerow([idx+1, val])
        writer.writerow([])
        writer.writerow(["Stats", "Value"])
        writer.writerow(["Avg(s)", avg_t])
        writer.writerow(["Min(s)", min_t])
        writer.writerow(["Max(s)", max_t])
        writer.writerow(["Std(s)", std_t])
        writer.writerow(["Power", power_val])
        writer.writerow(["Port", port])
        writer.writerow(["Baud", args.baud])
    
    print(f"\n✓ Results saved to: {args.out}")
    print(f"✓ Debug log saved to: {debug_log_path.absolute()}")


if __name__ == "__main__":
    main()
