
# define color library for time display
time_display_colors = {
    "gt 1day":      {"color": 0x154411, "trigger": 86400},
    "gt 1hr":       {"color": 0x33932A, "trigger": 86400},  # 1 day
    "normal":       {"color": 0x3b7a35, "trigger": 3600},   # 60 min
    "warning":      {"color": 0xFCFC3F, "trigger": 600},    # 10 min
    "alert":        {"color": 0xCC0000, "trigger": 300},    # 5 min
    "in progress":  {"color": 0x0000FF, "trigger": 0},
    "No meeting":   {"color": 0x035400, "trigger": 0}
}