# Sourced by airc. cmd_reminder — idle-message-nudge cadence control.
#
# Function exported back to airc's dispatch:
#   cmd_reminder  — show / set / pause / disable the auto-nudge interval
#                   that the monitor loop emits when the room has been
#                   silent for N seconds. `airc reminder 300` sets it to
#                   5 min, `off`/`pause` disable, no-arg shows current.
#
# External cross-references (call-time): die, ensure_init, get_config_val,
# set_config_val, AIRC_REMINDER (env override).
#
# Extracted from airc as part of #152 Phase 3 file split — the final
# structural sweep that takes the bash top-level back below ~1500 lines.

cmd_reminder() {
  ensure_init
  local arg="${1:-status}"
  local reminder_file="$AIRC_WRITE_DIR/reminder"

  case "$arg" in
    -h|--help)
      echo "Usage:"
      echo "  airc reminder              show current state"
      echo "  airc reminder <seconds>    set interval (e.g. 300)"
      echo "  airc reminder pause        pause reminders without losing the saved interval"
      echo "  airc reminder off          disable reminders entirely"
      return 0 ;;
    off|0)
      rm -f "$reminder_file"
      echo "  Reminders off."
      ;;
    pause)
      echo "0" > "$reminder_file"
      echo "  Reminders paused. 'airc reminder <seconds>' to resume."
      ;;
    status)
      if [ -f "$reminder_file" ]; then
        local val; val=$(cat "$reminder_file")
        if [ "$val" = "0" ]; then
          echo "  Reminders paused."
        else
          echo "  Reminder every ${val}s."
        fi
      else
        echo "  Reminders off."
      fi
      ;;
    *)
      # Defense in depth: only accept positive-integer seconds. Same
      # anti-pattern as cmd_channel — without this, `airc reminder
      # --foo` (any flag-shaped token we don't enumerate) would be
      # written into the reminder file as the interval.
      case "$arg" in
        ''|*[!0-9]*)
          echo "  Refusing to set reminder interval to '$arg' — must be a positive integer (seconds)." >&2
          echo "  Try: airc reminder --help" >&2
          return 2 ;;
      esac
      echo "$arg" > "$reminder_file"
      echo "  Reminder every ${arg}s if no messages."
      ;;
  esac
}
