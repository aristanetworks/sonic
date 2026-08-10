#!/bin/bash
# Switch CPU Utility Script for BMC platforms
# Provides utilities to manage the switch host CPU from BMC
# Uses the HostSwitchModule Python platform API via Chassis
#
# Usage: switch_cpu_utils.sh <command> [options]

set -e

# Script metadata
SCRIPT_NAME="$(basename "$0")"
LOG_TAG="switch-cpu-utils"

#######################################
# Print usage information
#######################################
usage() {
    cat << EOF
Usage: ${SCRIPT_NAME} <command> [options]

Switch CPU management utilities for BMC platforms.
This script uses the HostSwitchModule platform API.

Commands:
    power-on            Power on switch CPU (bring out of reset)
    power-off           Power off switch CPU (put into reset)
    power-cycle         Power cycle switch CPU
    system-power-cycle  Perform a full system power cycle
    status              Show switch CPU operational status
    help                Show this help message

Options:
    -h, --help          Show this help message

Examples:
    ${SCRIPT_NAME} power-on
    ${SCRIPT_NAME} power-cycle
    ${SCRIPT_NAME} system-power-cycle
    ${SCRIPT_NAME} status

EOF
}

#######################################
# Execute Python platform API command
#######################################
execute_python_command() {
    local command="$1"

    python3 << EOF
import sys

try:
    from sonic_platform.chassis import Chassis

    chassis = Chassis()
    if not chassis.is_bmc():
        print("ERROR: This command is only supported on BMC platforms.", file=sys.stderr)
        sys.exit(1)

    module = chassis.get_module(0)

    if "${command}" == "power-on":
        result = module.set_admin_state(True)
        if result:
            print("Switch CPU powered on successfully")
            sys.exit(0)
        else:
            print("ERROR: Failed to power on switch CPU", file=sys.stderr)
            sys.exit(1)

    elif "${command}" == "power-off":
        result = module.set_admin_state(False)
        if result:
            print("Switch CPU powered off successfully")
            sys.exit(0)
        else:
            print("ERROR: Failed to power off switch CPU", file=sys.stderr)
            sys.exit(1)

    elif "${command}" == "power-cycle":
        result = module.do_power_cycle()
        if result:
            print("Switch CPU power cycle completed successfully")
            sys.exit(0)
        else:
            print("ERROR: Failed to power cycle switch CPU", file=sys.stderr)
            sys.exit(1)

    elif "${command}" == "system-power-cycle":
        result = module.do_system_power_cycle()
        if result:
            print("System power cycle triggered successfully")
            sys.exit(0)
        else:
            print("ERROR: Failed to trigger system power cycle",
                  file=sys.stderr)
            sys.exit(1)

    elif "${command}" == "status":
        status = module.get_oper_status()
        name = module.get_name()
        desc = module.get_description()

        print("Switch CPU Status:")
        print(f"  Name:             {name}")
        print(f"  Description:      {desc}")
        print(f"  Operational State: {status}")

        if status == module.MODULE_STATUS_ONLINE:
            print("  Interpretation:   CPU is OUT OF RESET (running)")
        elif status == module.MODULE_STATUS_OFFLINE:
            print("  Interpretation:   CPU is IN RESET (held in reset)")
        elif status == module.MODULE_STATUS_FAULT:
            print("  Interpretation:   ERROR reading CPU status")
        else:
            print(f"  Interpretation:   Unknown status ({status})")

        sys.exit(0)

    else:
        print(f"ERROR: Unknown command '{command}'", file=sys.stderr)
        sys.exit(1)

except ImportError as e:
    print(f"ERROR: Failed to import platform modules: {e}", file=sys.stderr)
    print("Make sure the platform module is installed correctly", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
EOF

    return $?
}

#######################################
# Main function
#######################################
main() {
    if [ $# -eq 0 ]; then
        echo "ERROR: No command specified" >&2
        echo ""
        usage
        exit 1
    fi

    COMMAND="$1"
    shift

    case "${COMMAND}" in
        power-on)
            logger -t ${LOG_TAG} "Executing power-on command via HostSwitchModule"
            execute_python_command "power-on"
            ;;
        power-off)
            logger -t ${LOG_TAG} "Executing power-off command via HostSwitchModule"
            execute_python_command "power-off"
            ;;
        power-cycle)
            logger -t ${LOG_TAG} "Executing power-cycle command via HostSwitchModule"
            execute_python_command "power-cycle"
            ;;
        system-power-cycle)
            logger -t ${LOG_TAG} "Executing full system power-cycle command via HostSwitchModule"
            execute_python_command "system-power-cycle"
            ;;
        status)
            execute_python_command "status"
            ;;
        reset-out)
            echo "NOTE: 'reset-out' is deprecated, use 'power-on' instead" >&2
            logger -t ${LOG_TAG} "Executing power-on command (via legacy reset-out)"
            execute_python_command "power-on"
            ;;
        reset-in)
            echo "NOTE: 'reset-in' is deprecated, use 'power-off' instead" >&2
            logger -t ${LOG_TAG} "Executing power-off command (via legacy reset-in)"
            execute_python_command "power-off"
            ;;
        reset-cycle)
            echo "NOTE: 'reset-cycle' is deprecated, use 'power-cycle' instead" >&2
            logger -t ${LOG_TAG} "Executing power-cycle command (via legacy reset-cycle)"
            execute_python_command "power-cycle"
            ;;
        help|--help|-h)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: Unknown command '${COMMAND}'" >&2
            echo ""
            usage
            exit 1
            ;;
    esac
    exit $?
}

main "$@"
