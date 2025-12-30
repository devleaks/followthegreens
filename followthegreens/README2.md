Preset runway lights to

      - sim/operation/rwy_lights_off
      - sim/operation/rwy_lights_lo
      - sim/operation/rwy_lights_med
      - sim/operation/rwy_lights_hi


cmdref = xp.findCommand("sim/operation/rwy_lights_med")
if cmdref is not None:
    xp.commandOnce(cmdref)
    