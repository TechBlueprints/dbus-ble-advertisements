# List of available services and their paths

This documents lists data available on the Venus OS D-Bus.

The data is published by multiple services. For example each solar charger will have its own service on the D-Bus. As will a VE.Bus inverter/charger system, and-so-forth.

This list is probably not complete, in case you miss something you need, welcome to figure it out (ie. login to a device, and run [dbus -y](https://github.com/victronenergy/venus/wiki/commandline-introduction#working-with-d-bus) ), and then add it here.

And, besides `dbus -y` and `dbus-spy`, see also the Modbus-TCP excelsheet, available on our website. It also contains lots of details. Another reliable source are the gui qml pages.

Notes:
- not all paths are available for each type of device. For example a PV Inverter: in case the data on the D-Bus comes from an ethernet connected Fronius, there will be a Fronius device type on the D-Bus. But in case the PV Inverter is actually a Carlo Gavazzi energy meter configured to be measuring a PV Inverter, there is no Fronius Status code (of course).
- SI units are used for all measurements, with these exceptions: Energy is in kWh and temperature is in degrees Celsius.

Disclaimer on the stability of path naming & structure: we give no warranty about these paths and function to be the same for ever. Of course we will not change them often and/or without good reasons.

Index:
- [generic](#generic-paths)
- [error codes](#error-codes)
- [system](#system)
- [ess](#ess-formerly-called-hub-4)
- [settings](#settings)
- [vebus](#vebus-systems-multis-quattros-inverters)  (inverter/charger)
- [multi](#multi-rs-and-other-future-new-inverterchargers) (Multi RS and other future inverter/chargers, including external transfer switch)
- [acsystem](#acsystem) (Managing service for Multi-RS and other future inverter/chargers)
- [inverter](#inverter) (VE.Direct inverters & Inverter RS)
- [battery](#battery)
- [solar chargers](#solar-chargers)
- [DCDC converters](#dcdc-converters)
- [pvinverters](#pv-inverters)
- [ac chargers](#ac-chargers)
- [grid (and genset) meter](#grid-and-genset-meter)
- [temperatures](#temperatures)
- [meteo](#meteo)
- [tank levels](#tank-levels)
- [(diesel) generator](#generator-data)
- [generator start/stop](#generator-startstop)
- [vecan-xxx](#vecan-xxx)
- [alternator, dcsource](#alternator-and-dcsource)
- [fuelcell](#fuelcell)
- [motordrive](#motordrive)
- [dcsystem](#dcsystem)
- [dcload](#dcload)
- [evcharger](#evcharger)
- [heatpump](#heatpump)
- [switch](#switch) and `/SwitchableOutput` API
- [rvc](#rvc-xxx)
- [platform](#platform)
- [gps](#gps)
- [ble](#ble)

## Generic paths
```
/ProductName
/CustomName
/Mgmt/Connection
/Mgmt/ProcessName
/Mgmt/ProcessVersion
/Connected
/DeviceInstance
/ProductId
/Serial
/HardwareVersion
/FirmwareVersion
```

See [[dbus-api]] for more details.

## System
The system service is published by the [dbus-systemcalc-py](https://github.com/victronenergy/dbus-systemcalc-py) process. It takes the various readings like SOC, Battery voltages and other things from other processes, and then republishes these readings on the D-Bus. The System service is also where the System Overview pages in the GUI, and the VRM Dashboard get their data.

```
com.victronenergy.system
```

AC related paths:
```
/Ac/ActiveIn/Source             <- The active AC-In source of the multi.
                                   0:not available, 1:grid, 2:genset,
                                   3:shore, 240: inverting/island mode.
                                   This value is determined by matching
                                   the active input on the multi with the
                                   AC Input types as configured in the 
                                   System setup menu. Some notes:
                                   1) 0:not available means a config
                                      error by the user: he configured
                                      that input as not in use while it is.
                                   2) 240: inverting/island mode will be added
                                      in version v2.12~26.
                                      https://github.com/victronenergy/venus-private/issues/21
/Ac/ActiveIn/FeedbackEnabled    <- 0: Excess PV will not be fed into the grid
                                   1: Excess PV (either AC- or DC-coupled) will be fed into the grid
                                   Note: This is a summary of the ESS settings for VE.Bus systems, or the config of a Multi-RS, so that
                                   there is a single place where this information can always be found.
/Ac/HasAcLoads                  <- 0: No known AC loads, probably a DC-only system. User interfaces can hide part of the display.
                                   1: One or more AC loads might be present (an inverter or inverter/charger is present, or 
                                      a measured acload, evcharger or heatpump is present. User interfaces should display loads.
/Ac/Consumption/L1/Power        <- DEPRECATED. Total of /ConsumptionOnInput & 
                                   /ConsumptionOnOutput
/Ac/Consumption/L2/Power
/Ac/Consumption/L3/Power
/Ac/Consumption/NumberOfPhases  <- Either 1 (single phase), 2 (split-phase) or
                                   3 (three-phase)
/Ac/ConsumptionOnInput/*        <- Same subpaths as /Ac/Consumption
/Ac/ConsumptionOnOutput/*       <- Same subpaths as /Ac/Consumption
/Ac/Genset/*                    <- Same subpaths as /Ac/Consumption, and two more:
/Ac/Genset/ProductId
/Ac/Genset/DeviceType
/Ac/Grid/*                      <- Same subpaths as /Ac/Consumption, and two more:
/Ac/Grid/ProductId              <- Meter product id
/Ac/Grid/DeviceType             <- Meter device type. Invalid if Grid is not measured by an energy meter. 0 for generic grid meter.
/Ac/PvOnGenset/*                <- Same subpaths as /Ac/Consumption
/Ac/PvOnGrid/*                  <- Same subpaths as /Ac/Consumption
/Ac/PvOnOutput/*                <- Same subpaths as /Ac/Consumption
```

AC-input information (for use by user interfaces)
```
Ac/In/0/Connected      -> Whether the first AC input is connected (0=disconnected, 1=connected)
Ac/In/0/DeviceInstance -> DeviceInstance of the service performing the measurements for this input
Ac/In/0/ServiceName    -> Name of service performing the measurements for this input
Ac/In/0/ServiceType    -> Type of service (vebus,grid,genset,multi)
Ac/In/0/Source         -> The source connected to the first input, 0=not used, 1=Grid, 2=Generator, 3=Shore
Ac/In/1/Connected      -> Whether the second AC input is connected (invalid if no second input supported)
Ac/In/1/DeviceInstance -> DeviceInstance of the service performing the measurements for this input
Ac/In/1/ServiceName    -> Name of service performing the measurements for this input
Ac/In/1/ServiceType    -> Type of service (vebus,grid,genset,multi)
Ac/In/1/Source         -> The source connected to the second input, 0=not used, 1=Grid, 2=Generator, 3=Shore
```

DC & main battery related paths:
```
/Dc/Battery/Alarms/CircuitBreakerTripped   <- Something special
/Dc/Battery/Capacity           <- The total battery capacity published by the selected battery monitor,
                                  measured in Ah.
/Dc/Battery/ConsumedAmphours
/Dc/Battery/Current
/Dc/Battery/Power
/Dc/Battery/Soc
/Dc/Battery/State
/Dc/Battery/Temperature
/Dc/Battery/TimeToGo           <- in seconds, until battery SOC reaches "SOC relay/discharge floor" value.  Capped at 864000 (10 days) when battery is not discharging
/Dc/Battery/Voltage
/Dc/Charger/Power
/Dc/Pv/Current                 <- total output current of all
                                  connected solar chargers
/Dc/Pv/Power                   <- same, but then the power
/Dc/System/Power               <- see manual, has DC system
/Dc/Vebus/Current              <- charge/discharge current from
                                  the VE.Bus system
/Dc/Vebus/Power                <- same, but then the power

/Dc/InverterCharger/Power      <- The overall power used by inverter/chargers, including Multi, Multi RS, Inverter RS and other inverters
                                  Use this instead of the Vebus power, or Service, when showing a system overview.
/Dc/InverterCharger/Current    <- The current value for the above power 
```

Above paths all relate to the main aka central battery in a system. It is
possible to have more than one battery. Normally not in an ESS system, but other
applications, especially boats, have more. For example two starter batteries + a 
main service battery. For that there is the Settings -> System setup -> Battery measurements menu.

Related path:
```
/Batteries                        -> All batteries in the system (used in gui-v2 and html5-app and VRM)
                                     Use /Batteries in places where you want to show all batteries.

/AvailableBatteries               -> List of all battery measurements, used in Settings -> System setup -> Battery measurements.
```


Paths related to the Settings -> System setup -> Battery selection menu:
```
/ActiveBatteryService
/AutoSelectedBatteryMeasurement
/AutoSelectedBatteryService
/AvailableBatteryMeasurements
/AvailableBatteryServices
```

Indicators of various automatic functions such as enhancing or syncing the
VE.Bus SOC. See user manual for more info.

```
/Control/ExtraBatteryCurrent -> 0: no syncing, 1: solar charger current synced with Multi to improve SOC
/Control/SolarChargeCurrent  -> 0: no limiting, 1: solar charger limited by user setting or intelligent battery
/Control/SolarChargeVoltage  -> 0: no control, 1: solar charger voltage is controlled by intelligent battery or Multi
/Control/VebusSoc            -> 0: no syncing, 1: battery SOC is synced with the Multi
/Control/BatteryCurrentSense -> 0: Disabled (battery current is NOT sent to solar chargers).
                                1: Disabled because External control (ESS or intelligent battery) is used.
                                2: Disabled because there are no compatible solar chargers.
                                3: Disabled because a suitable battery monitor is not available.
                                4: Enabled (battery current is sent to solar chargers to improve tail detection).
```

Aggregated System State, used to display and record a more comprehensive view of what the system is doing. This mostly mirrors VE.Bus states, but adds more. It also breaks out separate conditions as flags.
```
/SystemState/State                 ->   0: Off
                                   ->   1: Low power
                                   ->   2: VE.Bus Fault condition
                                   ->   3: Bulk charging
                                   ->   4: Absorption charging
                                   ->   5: Float charging
                                   ->   6: Storage mode
                                   ->   7: Equalisation charging
                                   ->   8: Passthru
                                   ->   9: Inverting
                                   ->  10: Assisting
                                   -> 244: Battery Sustain (because Prefer Renewable Energy is enabled)
                                   -> 252: External control
                                   -> 256: Discharging
                                   -> 257: Sustain (battery voltage dropped below ESS dynamic cut-off)
                                   -> 258: Recharge
                                   -> 259: Scheduled recharge
```

System State flags:
```
/SystemState/BatteryLife           -> BatteryLife is active (in Settings->ESS->Mode)
/SystemState/ChargeDisabled        -> BMS has disabled charging
/SystemState/DischargeDisabled     -> BMS has disabled discharge
/SystemState/LowSoc                -> Battery at minimum configured SoC (Settings->ESS->Actual state of charge limit)
/SystemState/SlowCharge            -> Slow-charging from grid (if battery has been left discharged for too long).
/SystemState/UserChargeLimited     -> User configured a charge limit of 0
/SystemState/UserDischargeLimited  -> User configured a maximum inverter power of 0

```

Timers:
```
/Timers/TimeOnGrid      -> Time spent connect to the grid since last reboot (in seconds)
/Timers/TimeOnGenerator -> Time spent on generator power since last reboot (in seconds)
/Timers/TimeOnInverter  -> Time spent inverting (grid disconnected) since last reboot (in seconds)
/Timers/TimeOff         -> Time that the inverter was off since last reboot (in seconds)
```

IO / hardware abstraction:
```
/Buzzer/State
/Relay/0/State
/Relay/1/State
```

Other:
```
/SystemType                       -> Text string indicating hub-type corresponding with /Hub
/Hub                              -> 1: Hub-1, 2: Hub-2, 3: Hub-3, 4: ESS
/VebusInstance                    -> The VRM DeviceInstance of the VE.Bus service; for use over mqtt.
/VebusService                     -> Returns the service name of the vebus service
/PvInvertersProductIds            -> Returns a list of product ids for connected PV-inverters
/AutoSelectedBatteryMeasurement   -> The service used for battery voltage measurements and V-sense synchronisation.
/GpsService                       -> The auto selected "best" GPS service, being the one with lowest device
                                     instance and still a fix [1]. Used by the gui-v2 boat page [2].
                                     It contains the full service name, for example: com.victronenergy.gps.ve_ttyUSB0
/GpsSpeed                         -> The speed of the best GPS in m/s
```

[1] https://github.com/victronenergy/dbus-systemcalc-py/blob/master/delegates/gps.py
[2] https://github.com/victronenergy/gui-v2/blob/main/pages/boat/Gps.qml (or not, at the time of writing, in which
    case it will be fixed soon.

## ESS (formerly called Hub-4)
When writing functions that manipulate ESS, make sure to study the ESS manual and the Advanced ESS manual which documents mode 2 & 3.

In addition to these operational paths, also see the ESS related paths in [settings](#settings).
```
com.victronenergy.hub4

/PvPowerLimiterActive        <- In the GUI this is visible as Fronius Zero-feed in active
/MaxChargePower              <- Active maximum charge power limit 
/MaxDischargePower           <- Active maximum discharge power limit
/Overrides/ForceCharge       <- Used by scheduled charging and DynamicEss to activate charging
/Overrides/MaxDischargePower <- Used by scheduled charging and DynamicEss to limit DC discharge power
/Overrides/Setpoint          <- Used by DynamicEss to override the AC Power setpoint; Can also be used by users when DynamicEss is not used.
/Pv/Disable                  <- Disable all PV-inverters controlled by hub4control

Deprecated paths (use the same paths in .settings/Settings/CGWacs tree instead):
/State
/AcPowerSetpoint
/MaxChargePercentage
/MaxChargePower
/MaxDischargePercentage
/MaxDischargePower
```

## Settings
See [localsettings](https://github.com/victronenergy/localsettings) for source.

Note that are many more settings than documented here.

gui-v1/gui-v2 related settings:
```
com.victronenergy.settings

Settings/Gui/RunningVersion:  the gui that the user has configured in the UI (Settings -> Display -> User Interface)
                              1 = gui-v1, 2 = gui-v2.
                              Note that in some situations a user might have configured to prefer X, but actually another version
                              is running. For example because gui-v2 has not always been shipped in official releases, hence
                              no matter what preference is here in the settings, gui-v1 will be running regardless. 
                              Another situation is Cerbo GX without GX Touch: since gui-v2 cannot run without a framebuffer,
                              gui-v1 is started on Cerbos without GX Touch display, even though user selected gui-v2. User will
                              never notice that; and his preference for gui-v2 does help him elsewhere: Remote Console on LAN also
                              looks at this same setting.
                              For systems that need to know which gui is actually running, such as VRM, we have this second path on dbus:

com.victronenergy.platform  Gui/RunningVersion
                              This holds the actually running version on the GX itself. 1 = gui-v1 is running. 2 = gui-v2 is running.
                              note that for devices where gui-v1 is needed (CCGX) this is always 1.

                            Gui/OnScreenGuiv2Supported
                              This allows the wasm version to determine if gui-v2 can be started on
                              a screen or if only the remote console on LAN version is switched.
```

ESS related settings:
```
com.victronenergy.settings

/Settings/CGwacs/AcPowerSetPoint                  <- User setting: Grid set-point; Also see com.victronenergy.hub/Overrides/Setpoint.
/Settings/CGwacs/BatteryLife/DischargedSoc        <- Deprecated
/Settings/CGwacs/BatteryLife/DischargedTime       <- Internal
/Settings/CGwacs/BatteryLife/Flags                <- Internal
/Settings/CGwacs/BatteryLife/MinimumSocLimit      <- User setting: Minimum Discharge SOC
/Settings/CGwacs/BatteryLife/SocLimit             <- Output of the BatteryLife algorithm (read only)
/Settings/CGwacs/BatteryLife/State                <- ESS state (read & write, see below)
/Settings/CGwacs/Hub4Mode                         <- ESS mode (read & write, see below)
/Settings/CGwacs/MaxChargePercentage              <- Deprecated
/Settings/CGwacs/MaxChargePower                   <- User setting: Max Charge Power
/Settings/CGwacs/MaxDischargePercentage           <- Deprecated
/Settings/CGwacs/MaxDischargePower                <- User setting: Max Inverter Power
/Settings/CGwacs/OvervoltageFeedIn                <- User setting: Feed-in excess solar charger power (yes/no)
/Settings/CGwacs/PreventFeedback                  <- User setting: PV Inverter Zero Feed-in (on/off)
/Settings/CGwacs/RunWithoutGridMeter              <- User setting: Grid meter installed (on/off)
```

**ESS mode (/Settings/CGwacs/Hub4Mode):**
```
1: Optimized mode or 'keep batteries charged' and phase compensation enabled 
2: Optimized mode or 'keep batteries charged' and phase compensation disabled
3: External control
```

**ESS state (/Settings/CGwacs/BatteryLife/State):**

This path can both be read from, and written to.

For reading the ESS state:
```
0: No longer used.

Optimized mode with BatteryLife:
1: Value set by the GUI when BatteryLife is enabled. Hub4Control uses it to find the right BatteryLife state (values 2-7) based on system state
2: Self consumption
3: Self consumption, SoC exceeds 85%
4: Self consumption, SoC at 100%
5: SoC below BatteryLife dynamic SoC limit
6: SoC has been below SoC limit for more than 24 hours. Charging with battery with 5amps
7: Multi/Quattro is in sustain
8: Recharge, SOC dropped 5% or more below MinSOC.

Keep batteries charged mode:
9: 'Keep batteries charged' mode enabled

Optimized mode without BatteryLife:
10: Self consumption, SoC at or above minimum SoC
11: Self consumption, SoC is below minimum SoC
12: Recharge, SOC dropped 5% or more below minimum SoC
```

For changing the ESS state:
```
1:  Change the ESS mode to "Optimized (with BatteryLife)"
9:  Change the ESS mode to "Keep Batteries Charged"
10: Change the ESS mode to "Optimized (without BatteryLife)"
```

So to summarise:
```
To set the system to External Control:
- write 3 to /Settings/CGwacs/Hub4Mode

To set the system to Keep Batteries charged:
- write 1 or 2 to /Settings/CGwacs/Hub4Mode (1 enabled phase compensation; 2 disables it).
- write 9 to /Settings/CGwacs/BatteryLife/State

To set the system to Optimized
- write 1 or 2 to /Settings/CGwacs/Hub4Mode (1 enabled phase compensation; 2 disables it).
- write 1 or 10 to /Settings/CGwacs/BatteryLife/State (1 for BatteryLife, 10 for without).
```

## VE.Bus systems (Multis, Quattros, Inverters)
```
com.victronenergy.vebus

AC Input measurements:
/Ac/ActiveIn/*                          <- The ActiveIn paths show the readings of the
                                           current active input. Readings for the other,
                                           AC input are, unfortunately, not available.
                                           The hardware can only measure the data for the
                                           active one (which can also be not connected - ie.
                                           ac-ignored).
/Ac/ActiveIn/L1/F                       <- Frequency
/Ac/ActiveIn/L1/I                       <- Current
/Ac/ActiveIn/L1/P                       <- Real power (or not, for very old devices, see
                                           /Ac/PowerMeasurementType, further below).
/Ac/ActiveIn/L1/S                       <- Note that all */S paths only change their
                                           value. No update of the change is transmitted
                                           in order to reduce D-Bus load. (and we don't
                                           need nor use the /S paths anywhere).
/Ac/ActiveIn/L1/V
/Ac/ActiveIn/Lx/*                       <- Same as L1

/Ac/ActiveIn/P                          <- Total power.
/Ac/ActiveIn/S                          <- Total apparent power (and see */S node above)

AC Output measurements:
/Ac/Out/L*/*                            <- Same as ActiveIn, and also same */S paths
                                           restriction as explained above.
                                           There is only a measurement for the total output
                                           power; ie AC out1 & AC out 2 are not independently
                                           measured.

ActiveIn other paths:
/Ac/ActiveIn/Connected                  <- 0 when inverting, 1 when connected to
                                           an AC in. Path is not available when
                                           VE.Bus is connected via VE.Can.
                                           DEPRECATED in favor of /Ac/ActiveIn/ActiveInput

/Ac/ActiveIn/ActiveInput                <- Active input: 0 = ACin-1, 1 = ACin-2,
                                           240 is none (inverting).
                                           Note open issue:
                                           https://github.com/victronenergy/venus-private/issues/21
/Ac/ActiveIn/CurrentLimit               <- DEPRECATED in favor of /Ac/In/[1 and 2] paths
/Ac/ActiveIn/CurrentLimitIsAdjustable   <- DEPRECATED in favor of /Ac/In/[1 and 2] paths
                                           0 when disabled in VEConfigure, or when
                                           there is a VE.Bus BMS or DMC, etc.

/Ac/In/1/CurrentLimit                   <- these are the new and current paths to control input
/Ac/In/1/CurrentLimitIsAdjustable          current limits.
/Ac/In/2/CurrentLimit
/Ac/In/2/CurrentLimitIsAdjustable

/Settings/SystemSetup/AcInput1          <- since approx v2.70 or v2.80, these paths exist and indicate the
/Settings/SystemSetup/AcInput2             type of that input: 0 (Not used), 1 (Grid), 2(Generator), 3(Shore).

/Ac/PowerMeasurementType                <- Indicates the type of power measurement used by the system. The
                                           best one, 4, is the method used for all recent hardware and software
                                           since 2018 or even earlier.
                                           0 = Apparent power only -> under the /P paths, apparent power
                                               is published.
                                           1 = Real power, but only measured by phase masters, and not
                                               synced in time. (And multiplied by number of units in
                                               parallel)
                                           2 = Real power, from all devices, but at different points in time
                                           3 = Real power, at the same time snapshotted, but only by the
                                               phase masters and then multiplied by number of units in
                                               parallel.
                                           4 = Real power, from all devices and at snaphotted at the same
                                               moment.

Ac ignore AC in control:
/Ac/Control/IgnoreAcIn1           <- 0=do not ignore, 1=ignore AcIn1, invalid=Not supported by Multifirmware
/Ac/Control/IgnoreAcIn2           <- 0=do not ignore, 1=ignore AcIn2, invalid=Not supported by Multifirmware
                                     NOTE: The /Ac/Control/IgnoreAcIn# dbus item is only available with Multi firmware version 502 and up.
                                           The actual ignore status is available on Ac/State/IgnoreAcIn# 

Ac state information:
/Ac/State/IgnoreAcIn1             <- 0 = AcIn1 is not ignored; 1 = AcIn1 is being ignored.
/Ac/State/IgnoreAcIn2             <- 0 = AcIn2 is not ignored; 1 = AcIn2 is being ignored.
                                     NOTE: AcIn can be ignored by "/Ac/Control/IgnoreAcIn#, Grid code, BMS control, Assistants and Virtual Switch 

Ac/State/SplitPhaseL2L1OutSummed  <- 0 = L1 and L2 output power values seperately available; 1 = L1+L2 power values summed together.
                                     NOTE: is available only in the 120V versions for the North American markets.
                                           On some models L2 output power can not be reported separately when not in Passthru
/Ac/State/SplitPhaseL2Passthru    <- 0 = L1+L2 shorted together; 1 = L2 connected to external L2; Invalid = unused in this configuration
                                     NOTE: Split Phase Passthru is available only in the 120V versions for the North American markets.



For all alarms: 0=OK; 1=Warning; 2=Alarm
Generic alarms:
/Alarms/HighDcCurrent                   <- 0=OK; 2=High DC current condition in one or more Multis/Quattros
/Alarms/HighDcVoltage                   <- 0= K; 2=High DC voltage
/Alarms/LowBattery                       
/Alarms/PhaseRotation                   <- 0=OK, 1=Warning when AC input phase rotation direction is wrong 
/Alarms/Ripple
/Alarms/TemperatureSensor               <- Battery temperature sensor alarm
 
Phase specific alarms:
/Alarms/L1/HighTemperature              <- inverter/charger high temperature alarm
/Alarms/L1/LowBattery
/Alarms/L1/Overload
/Alarms/L1/Ripple
/Alarms/L2/*                            <- same
/Alarms/L3/*                            <- same

Paths related to BMSes connected to the Multi or VE.Bus system (excluding Can-bus BMSes).
/Bms/AllowToCharge                      <- BMS allows the battery to be charged
/Bms/AllowToDischarge                   <- BMS allows the battery to be discharged
/Bms/BmsExpected                        <- Set if the Multi/Quattro is configured with a VE.Bus BMS.
/Bms/BmsType                            <- 1 = Two signal BMS; 2 = VE.Bus BMS
/Bms/Error                              <- BMS error code
/Bms/PreAlarm                           <- Raised a few seconds before the BMS disconnects on low battery

DC/Battery related information:
/Dc/0/Voltage                           <- Battery Voltage
/Dc/0/Current                           <- Battery current in Ampere, positive when charging
/Dc/0/Power                             <- Battery power in Watts, positive when charging
/Dc/0/Temperature                       <- Battery temperature in degrees Celsius

/Mode                                   <- Position of the switch.
                                           1=Charger Only;2=Inverter Only;3=On;4=Off
                                           Make sure to read CCGX manual, and limitations
                                           of this switch, for example when using a VE.Bus BMS.
/ModeIsAdjustable                       <- 0. Switch position cannot be controlled remotely (typically because a VE.Bus BMS is present).
                                           1. Switch position can be controlled remotely
/State                                  <- 0=Off;1=Low Power Mode;2=Fault;3=Bulk;4=Absorption;5=Float;
                                           6=Storage;7=Equalize;8=Passthru;9=Inverting;10=Power assist;
                                           11=Power supply mode;244=Sustain(Prefer Renewable Energy);252=External control
/VebusChargeState                       <- 1. Bulk
                                           2. Absorption
                                           3. Float
                                           4. Storage
                                           5. Repeat absorption
                                           6. Forced absorption
                                           7. Equalise
                                           8. Bulk stopped
/VebusSetChargeState                    <- 1. Force to Equalise. 1 hour 1, 2 or 4 V above
                                              absorption (12/24/48V). Charge current is limited
                                              to 1/4 of normal value. Will be followed by a normal
                                              24-hour float state.
                                           2. Force to Absorption, for maximum absorption time.
                                              Will be followed by a normal 24-hour float state.
                                           3. Force to Float, for 24 hours. 
                                           (from "Interfacing with VE.Bus products – MK2 Protocol" doc)

The new CurrentLimit paths, only available on VE.Bus 415 or later:
/Ac/In/1/CurrentLimit                   <- R/W for input current limit.
/Ac/In/1/CurrentLimit GetMin            <- not implemented!)
/Ac/In/1/CurrentLimit GetMax
/Ac/In/1/CurrentLimitIsAdjustable
/Ac/In/2/*                              <- same


LEDs: 0 = Off, 1 = On, 2 = Blinking, 3 = Blinking inverted
/Leds/Mains
/Leds/Bulk
/Leds/Absorption
/Leds/Float
/Leds/Inverter
/Leds/Overload
/Leds/LowBattery
/Leds/Temperature

BMS: only contains valid data if a VE.Bus BMS is present
/Bms/AllowToCharge     <- 0=No, 1=Yes
/Bms/AllowToDischarge  <- 0=No, 1=Yes
/Bms/BmsExpected       <- 0=No, 1=Yes
/Bms/Error             <- 0=No, 1=Yes

A full list of commonly used operational paths is available as
the modbusexcelsheet. See whitepaper section on our website.

More VE.Bus D-Bus documentation about ESS control and various
other more complex features is on the Victron internal wiki,
ccgx/specs/mk2-dbus.
```

## Multi RS and other future new inverter/chargers
```
com.victronenergy.multi

AC Input measurements:
/Ac/In/1/L1/V                           <- Voltage of AC IN1 on L1
/Ac/In/1/L1/F                           <- Frequency of AC IN1 on L1
/Ac/In/1/L1/I                           <- Current of AC IN1 on L1
/Ac/In/1/L1/P                           <- Real power of AC IN1 on L1
/Ac/In/n/Lx/*                           <- Same for every input and every phase

AC Input settings:
/Ac/In/n/CurrentLimit                   <- The input current limit of AC INn; n=1 => AC IN1
/Ac/In/n/CurrentLimit GetMin            <- Minimum allowed current limit
/Ac/In/n/CurrentLimit GetMax            <- Maximum allowed current limit
/Ac/In/n/CurrentLimitIsAdjustable       <- Reflects whether the current limit is adjustable or not
                                           0 when disabled in VictronConnect
/Ac/In/1/Type                           <- AC IN1 type: 0 (Not used), 1 (Grid), 2(Generator), 3(Shore)
/Ac/In/n/Type                           <- Same for every input

AC Output measurements:
/Ac/Out/Lx/*                            <- Same as Ac/In

ActiveIn paths:
/Ac/ActiveIn/ActiveInput                <- Active input: 0 = ACin-1, 1 = AC in2, 240 = not connected. 

Other AC paths:
Ac/NumberOfPhases
Ac/NumberOfAcInputs

For all alarms: 0=OK; 1=Warning; 2=Alarm
Generic alarms:
/Alarms/LowSoc                          <- Low state of charge
/Alarms/LowVoltage                      <- Low battery voltage
/Alarms/HighVoltage                     <- High battery voltage
/Alarms/LowVoltageAcOut                 <- Low AC Out voltage
/Alarms/HighVoltageAcOut                <- High AC Out voltage
/Alarms/HighTemperature                 <- High device temperature
/Alarms/Overload                        <- Inverter overload
/Alarms/Ripple                          <- High DC ripple
 
/Dc/0/Voltage                           <- Battery Voltage
/Dc/0/Current                           <- Battery current in Ampere, positive when charging
/Dc/0/Temperature                       <- Battery temperature in degrees Celsius

/Mode                                   <- Position of the switch.
                                           1=Charger Only;2=Inverter Only;3=On;4=Off
/State                                  <- Charger state
                                           0=Off
                                           2=Fault
                                           3=Bulk
                                           4=Absorption
                                           5=Float
                                           6=Storage
                                           7=Equalize
                                           8=Passthrough
                                           9=Inverting
                                           245=Wake-up
                                           25-=Blocked
                                           252=External control
/Soc                                    <- State of charge of internal battery monitor
/ErrorCode
/DeviceOffReason
/Relay/0/State                          

PV tracker information:
/NrOfTrackers
/Pv/0/V                                 <- PV array voltage from 1st tracker
/Pv/x/V                                 <- PV array voltage from tracker x+1; todays max number of trackers in a single Victron product is 4
/Pv/0/P                                 <- PV array power (Watts) from 1st tracker
/Pv/x/P                                 <- PV array power from tracker no. x+1
/Pv/0/MppOperationMode                  <- Operating mode of the 1st tracker (See /MppOperationMode below, since v3.??)
/Pv/x/MppOperationMode                  <- Operating mode of tracker no. x+1 (See /MppOperationMode below, since v3.??)
/Pv/0/Name                              <- Custom name of the 1st tracker
/Pv/x/Name                              <- Custom name tracker no. x+1
/Pv/Disable                             <- Disable all PV generation
/Yield/Power                            <- PV array power (Watts)
/Yield/User                             <- Total kWh produced (user resettable)
/Yield/System                           <- Total kWh produced (not resettable)
/MppOperationMode                       <- 0 = Off
                                           1 = Voltage or Current limited
                                           2 = MPPT Tracker active
                                           For products with multiple trackers, this is an aggregate of the separate tracker states. When one or more
                                           trackers are voltage/current limited, this value also shows voltage/current limited. If there is no tracker
                                           that is voltage/current limited, but one or more trackers are on (so mpp tracking), then the overall state
                                           is MPP tracking.
```
## Acsystem
(managing service for Multi-RS and other inverter/chargers)

Also see the project [README](https://github.com/victronenergy/dbus-acsystem/blob/master/README.md).

### Mode and settings
```
com.victronenergy.acsystem

/Ac/In/n/Type                     <--- Type of AC input configured in VictronConnect,
                                       1=Grid, 2=Genset, 3=Shore.
/Ac/In/n/CurrentLimit             <--- AC input current limit for input n
/Ac/In/1/CurrentLimitIsAdjustable <--- Whether current limit can be adjusted.
                                       All units must be adjustable otherwise
                                       this will be 0.
/Mode                             <--- Switch position. Sent to one RS only, the RSes sync this themselves
/Pv/Disable                       <--- Disable PV generation on all units in the system
/Ess/AcPowerSetpoint              <--- AC power setpoint ( returns back to fallback value from RS settings within 60 seconds )
/Ess/DisableFeedIn                <--- Disable grid feedin (at metering point)
/Ess/UseInverterPowerSetpoint     <--- InverterPowerSetpoint is used instead of
                                       AcPowerSetpoint. Used by DynamicEss.
/Ess/InverterPowerSetpoint        <--- How much DC to convert from/to AC, positive
                                       values charges the battery, negative
                                       discharges the battery. ( returns back to fallback value from RS settings within 60 seconds )
/Settings/Ess/MinimumSocLimit     <--- Minimum SOC limit for ESS
/Settings/Ess/Mode                <--- ESS mode
                                   * 0 = Optimised with BatteryLife
                                   * 1 = Optimised without BatteryLife
                                   * 2 = Keep Batteries Charged
                                   * 3 = External Control

/Settings/AlarmLevel/...          <--- Disable, warn, or only alarm.
```

`/Ess/UseInverterPowerSetpoint` toggles between `/Ess/InverterPowerSetpoint` and `/Ess/AcPowerSetpoint` as there can only be one active setpoint. If `/Ess/InverterPowerSetpoint` times out `/Ess/UseInverterPowerSetpoint` is cleared automatically. As long as you keep /Ess/InverterPowerSetpoint active, the /Ess/InverterPowerSetpoint won't clear


### Capabilities

```
/Capabilities/HasAcPassthroughSupport <--- All RS units support passthru
/Capabilities/HasDynamicEssSupport    <--- DynamicEss is supported
```

### Data
```
/State                   <--- Summarised state of the system
/Ac/ActiveIn/ActiveInput <--- Active AC input(s) on RS units. All units are
                              expected to be the same, otherwise this will
                              show invalid.
/Ac/In/n/Lx/I            <--- Total current drawn on phase x, input n
/Ac/In/n/Lx/P            <--- Total power drawn on phase x, input n
/Ac/In/n/P               <--- Total power drawn over all phases
/Ac/NumberOfAcInputs     <--- Number of AC inputs
/Ac/NumberOfPhases       <--- Number of phases
/Ac/Out/Lx/I             <--- Total current drawn on output
/Ac/Out/Lx/P             <--- Total power drawn on output

/Devices/x/Service     <--- List of service/instances that make up this service
/Devices/x/Instance
```

## Inverter
(vedirect inverters & Inverter RS)
```
com.victronenergy.inverter
/Alarms/LowVoltage          <- 0=No Alarm; 1=Warning; 2=Alarm
/Alarms/HighVoltage
/Alarms/LowTemperature
/Alarms/HighTemperature
/Alarms/Overload
/Alarms/Ripple
/Alarms/LowVoltageAcOut
/Alarms/HighVoltageAcOut

/Dc/0/Voltage             <- Battery voltage
/Ac/Out/L1/V              <- AC Output voltage
/Ac/Out/L1/I              <- AC Output current
/Ac/Out/L1/P              <- Not used on vedirect inverters 
/Mode                     <- Switch position: 1=Charger only,2=Inverter only;3=On;4=Off;5=Low Power/Eco;
                                              251=Passthrough;252=Standby;253=Hibernate
/State                    <- 0=Off; 1=Low Power; 2=Fault; 9=Inverting
/Relay/0/State            <- Not used on vedirect inverters
```

* Note on `/Mode`: A mppt is a charger only, so setting it to mode `1` will switch it on. A multi is both an inverter and a charger. Switching that to on requires setting it to mode `3`.

## Battery
```
com.victronenergy.battery

/Dc/0/Voltage               <- V DC
/Dc/0/Current               <- A DC positive when charged, negative when discharged
/Dc/0/Power                 <- W positive when charged, negative when discharged
/Dc/0/Temperature           <- °C Battery temperature (BMV-702 configured to read
                               temperature only)
/Dc/0/MidVoltage            <- V DC Mid voltage (BMV-702 configured to read midpoint
                               voltage only)
/Dc/0/MidVoltageDeviation   <- Percentage deviation

/Dc/1/Voltage               <- V DC - Starter voltage (BMV-702 configured to read starter
                               battery voltage only)

/ConsumedAmphours           <- Ah (BMV, Lynx BMS).
/Soc                        <- 0 to 100 % (BMV, BYD, Lynx BMS)
/TimeToGo                   <- Time to in seconds (BMV "SOC relay/discharge floor" value, Lynx BMS).  Max value 864,000 when battery is not discharging.

DVCC & BOL related paths. These are published by batteries.
/Info/MaxChargeCurrent      <- Charge Current Limit aka CCL 
                               (BYD, Lynx BMS and FreedomWon)
/Info/MaxDischargeCurrent   <- Discharge Current Limit aka DCL
                               (BYD, Lynx BMS and FreedomWon)
/Info/MaxChargeVoltage      <- Maximum voltage to charge to
                               (BYD, Lynx BMS and FreedomWon)
/Info/BatteryLowVoltage     <- Note that Low Voltage is ignored by the system
                               (BYD, Lynx BMS and FreedomWon)
/Info/ChargeRequest         <- Battery is extremely low and needs to be charged
                               (BYD, Pylontech and BlueNova)

For all alarms: 0=OK; 1=Warning; 2=Alarm
/Alarms/Alarm              <- Generic alarm condition (deprecated; ignored by GUI & VRM)
/Alarms/LowVoltage         <- BMV, BYD, Lynx BMS
/Alarms/HighVoltage        <- BMV, BYD, Lynx BMS
/Alarms/HighCellVoltage    <- BYD, Lynx BMS
/Alarms/LowStarterVoltage  <- BMV-702 configured to read starter battery voltage only
/Alarms/HighStarterVoltage <- BMV-702 configured to read starter battery voltage only
/Alarms/LowSoc             <- BMV, Lynx BMS
/Alarms/HighChargeCurrent  <- BYD
/Alarms/HighDischargeCurrent <- BYD
/Alarms/HighCurrent        <= Lynx Smart BMS
/Alarms/CellImbalance      <- BYD
/Alarms/InternalFailure    <- BYD
/Alarms/HighChargeTemperature <- BYD
/Alarms/LowChargeTemperature  <- BYD
/Alarms/LowCellVoltage     <- Lynx BMS
/Alarms/LowTemperature     <- BMV, Lynx BMS, BYD
/Alarms/HighTemperature    <- BMV, Lynx BMS, BYD
/Alarms/MidVoltage         <- Midpoint deviation, BMV only when configured to monitor
                              the midpoint.
/Alarms/Contactor          <- Lynx Smart BMS
/Alarms/BmsCable           <- Lynx Smart BMS; only used in Lynx Smart BMS NG, disabled in firmware (but still visible in dbus) for the 
                              other version.
/Alarms/HighInternalTemperature <- Lynx Smart BMS
/Alarms/FuseBlown          <- Lynx Shunt VE.Can

/Settings/HasTemperature
/Settings/HasStarterVoltage
/Settings/HasMidVoltage

/Relay/0/State             <- Read to see the state of the relay in the Battery Monitor. In case configured
                              to the "Remote" mode, using the VictronConnect App, the relay can be controlled
                              by writing to this path.
                              More information also here: https://www.victronenergy.com/live/venus-os:large#controlling_relays

/History/DeepestDischarge
/History/LastDischarge
/History/AverageDischarge
/History/ChargeCycles
/History/FullDischarges
/History/TotalAhDrawn
/History/MinimumVoltage
/History/MaximumVoltage
/History/TimeSinceLastFullCharge
/History/AutomaticSyncs
/History/LowVoltageAlarms
/History/HighVoltageAlarms
/History/LowStarterVoltageAlarms
/History/HighStarterVoltageAlarms
/History/MinimumStarterVoltage
/History/MaximumStarterVoltage
/History/DischargedEnergy
/History/ChargedEnergy

Lynx Smart BMS & Lynx Ion Only:
/State
/ErrorCode
/SystemSwitch
/Balancing
/System/NrOfBatteries
/System/BatteriesParallel
/System/BatteriesSeries
/System/NrOfCellsPerBattery
/System/MinCellVoltage
/System/MaxCellVoltage
/System/MinCellTemperature
/System/MaxCellTemperature
/Diagnostics/ShutDownsDueError
/Diagnostics/LastErrors/1/Error
/Diagnostics/LastErrors/2/Error
/Diagnostics/LastErrors/3/Error
/Diagnostics/LastErrors/4/Error
/Io/AllowToCharge
/Io/AllowToDischarge
/Io/ExternalRelay
/History/MinimumCellVoltage
/History/MaximumCellVoltage

Lynx Smart BMS:
/NrOfDistributors                    <= Number of connected distributors (up to 8)
                                        Note that this does not reflect which distributors are connected, 
                                        i.e. B & D can be present whithout A & B being present
/Distributor/A/Status                <= 0=Not available, 1=Connected, 2=No bus power, 3=Communications Lost
/Distributor/A/Alarms/ConnectionLost <= 0=Ok, 2=Alarm
/Distributor/A/Fuse/0/Name           <= UTF-8 string, limited to 16 bytes in firmware
/Distributor/A/Fuse/0/Status         <= 0=Not available, 1=Not used, 2=Ok, 3=Blown
/Distributor/A/Fuse/0/Alarms/Blown   <= 0=Ok, 2=Alarm
/Distributor/A/Fuse/n/*              <= Repeat for every fuse in the distributor
/Distributor/B/...                   <= Repeat for every distributor (A-E)
...
/Distributor/E/...
``` 

## Solar chargers
```
com.victronenergy.solarcharger

Number of trackers:
/NrOfTrackers: Number of trackers, usually 1 for all common MPPTs, and 2 or 4 for MPPT RS.

PV Array voltages, currents and state:
/Pv/V                  <- PV array voltage, path exists only for single tracker product (all common MPPTs)
/Pv/0/V                <- PV array voltage from 1st tracker
/Pv/x/V                <- PV array voltage from tracker x+1; today's max number of trackers in a single Victron product is 4.
/Pv/0/P                <- PV array power (Watts) from 1st tracker
/Pv/x/P                <- PV array power from tracker no. x+1. 
/Pv/0/MppOperationMode <- Operating mode of the 1st tracker (See /MppOperationMode below, since v3.00)
/Pv/x/MppOperationMode <- Operating mode of tracker no. x+1  (See /MppOperationMode below, since v3.00)
/Pv/0/Name             <- Custom name of the 1st tracker (since v3.??)
/Pv/x/Name             <- Custom name tracker no. x+1 (since v3.??)

/Yield/Power           <- Total PV power (Watts).
/MppOperationMode      <- 0 = Off
                          1 = Voltage or Current limited
                          2 = MPPT Tracker active (The maximum available power is taken from PV array)
                          For products with multiple trackers, this is an aggregate of the separate tracker states. When one or more
                          trackers are voltage/current limited, this value also shows voltage/current limited. If there is no tracker
                          that is voltage/current limited, but one or more trackers are on (so mpp tracking), then the overall state
                          is MPP tracking.

  Two examples:
  1) a solar charger with one tracker has 3 paths:
  /Pv/V
  /Yield/Power
  /MppOperationMode

  2) a solar charger with two trackers has 8 paths:
  /Pv/0/V
  /Pv/0/P
  /Pv/0/MppOperationMode
  /Pv/1/V
  /Pv/1/P
  /Pv/1/MppOperationMode
  /Yield Power
  /MppOperationMode

  deprecated per v2.80:
  /Pv/I                <- PV current (= /Yield/Power divided by /Pv/V)
  /Pv/x/I

External control:
/Link/NetworkMode    <- Bitmask
                        0x1 = External control
                        0x4 = External voltage/current control
                        0x8 = Controled by BMS (causes Error #67, BMS lost, if external control is interrupted).
/Link/BatteryCurrent <- When SCS is enabled on the GX device, the battery current is written here to improve tail-current detection.
/Link/ChargeCurrent  <- Maximum charge current. Must be written every 60 seconds. Used by GX device if there is a BMS or user limit.
/Link/ChargeVoltage  <- Charge voltage. Must be written every 60 seconds. Used by GX device to communicate BMS charge voltages.
/Link/NetworkStatus  <- Bitmask
                        0x01 = Slave
                        0x02 = Master
                        0x04 = Standalone
                        0x20 = Using I-sense (/Link/BatteryCurrent)
                        0x40 = Using T-sense (/Link/TemperatureSense)
                        0x80 = Using V-sense (/Link/VoltageSense)
/Link/TemperatureSense       <- When STS is enabled, the GX device will write the battery temperature here
/Link/TemperatureSenseActive <- Indicate when temperature sense is in use
/Link/VoltageSense           <- When SVS is active, the GX device will write the battery voltage here
/Link/VoltageSenseActive     <- INdicate when voltage sense is in use

Settings:
/Settings/BmsPresent         <- BMS in the system. External control is expected.
                                This happens automatically if NetworkMode is set to expect a BMS.
/Settings/ChargeCurrentLimit <- The maximum configured (non-volatile) charge current. This is the same as set by VictronConnect.

 
Other paths:
/Dc/0/Voltage     <- Actual battery voltage
/Dc/0/Current     <- Actual charging current
/Yield/User       <- Total kWh produced (user resettable)
/Yield/System     <- Total kWh produced (not resettable)
/Load/State       <- Whether the load is on or off
/Load/I           <- Current from the load output
/ErrorCode        <- 0=No error
                     1=Battery temperature too high
                     2=Battery voltage too high
                     3=Battery temperature sensor miswired (+)
                     4=Battery temperature sensor miswired (-)
                     5=Battery temperature sensor disconnected
                     6=Battery voltage sense miswired (+)
                     7=Battery voltage sense miswired (-)
                     8=Battery voltage sense disconnected
                     9=Battery voltage wire losses too high
                     17=Charger temperature too high
                     18=Charger over-current
                     19=Charger current polarity reversed
                     20=Bulk time limit reached
                     22=Charger temperature sensor miswired
                     23=Charger temperature sensor disconnected
                     34=Input current too high
                     https://www.victronenergy.com/live/mppt-error-codes
/State            <- 0=Off
                     2=Fault
                     3=Bulk
                     4=Absorption
                     5=Float
                     6=Storage
                     7=Equalize
                     252=External control
/History/*        <- Contains values about the last month's history
                     (Only for VE.Direct solarchargers)
/Mode             <- 1=On; 4=Off
                     Writeable for both VE.Direct & VE.Can solar chargers

/DeviceOffReason  <- Bitmask indicating the reason(s) that the MPPT is in Off State
                     0x01 = No/Low input power
                     0x02 = Disabled by physical switch
                     0x04 = Remote via Device-mode or push-button
                     0x08 = Remote input connector
                     0x10 = Internal condition preventing startup
                     0x20 = Need token for operation
                     0x40 = Signal from BMS
                     0x80 = Engine shutdown on low input voltage
                     0x100 = Converter is off to read input voltage accurately
                     0x200 = Low temperature
                     0x400 = no/low panel power
                     0x800 = no/low battery power
                     0x8000 = Active alarm

/Relay/0/State    <- Read to see the state of the relay in the Battery Monitor. In case configured
                     to the "Remote" mode, using the VictronConnect App [SEE NOTE], the relay can be controlled
                     by writing to this path.
                     More information also here: https://www.victronenergy.com/live/venus-os:large#controlling_relays

                     NOTE: currently, 2022-08-17, VictronConnect does not yet offer that settings. It is
                     planned for later in 2022. Until then, the relay control in the MPPT cannot be set to this mode by
                     any available ready to use Victron software.
```

## DCDC converters
This includes the Orion XS non-isolated DC/DC charger. The Orion XS can be configured as Power Supply or as Charger. When it is configured as Charger, /Settings/OutputBattery will be 1 to indicate that the input is connected to the main battery and the output connected to some auxiliary battery.

```
com.victronenergy.dcdc
/Capabilities/Capabilities1
/Dc/0/Current                <- Output current
/Dc/0/Power                  <- Output power
/Dc/0/Voltage                <- Output voltage
/Dc/In/I                     <- Input current
/Dc/In/P                     <- Input power
/Dc/In/V                     <- Input voltage
/DeviceOffReason             <- Reason why device is off; See solar charger section
/ErrorCode                   <- Error code; See solar charger section
/Mode                        <- 1=On; 4=Off
/Settings/DeviceFunction     <- 0=Charger(=Alternator), 1=PSU(=dcdc)
/Settings/OutputBattery      <- 0=main battery, 1=aux battery (will always be 1 for .dcdc, available when /Settings/DeviceFunction is 0)
/State                       <- 0=Off
                                2=Fault
                                3=Bulk
                                4=Absorption
                                5=Float
                                6=Storage
                                7=Equalize
                               11=Psu
/History/*                   <- Contains information about the charging cycles (available when /Settings/DeviceFunction is 0)
```

## PV Inverters
```
com.victronenergy.pvinverter

/Ac/Energy/Forward     <- kWh  - Total produced energy over all phases
/Ac/Power              <- W    - Total power of all phases, preferably real power
/Ac/L1/Current         <- A AC
/Ac/L1/Energy/Forward  <- kWh
/Ac/L1/Power           <- W
/Ac/L1/Voltage         <- V AC
/Ac/L2/*               <- same as L1
/Ac/L3/*               <- same as L1

/Ac/Current            <- A AC - Deprecated
/Ac/Voltage            <- V AC - Deprecated

/Ac/MaxPower           <- Max rated power (in Watts) of the inverter
/Ac/PowerLimit         <- Used by the Fronius Zero-feedin feature, see ESS manual.
                          Path must be invalid or non-existent for PV Inverters
                          that do not implement Zero Feed-in power control. ( returns back to fallback value within 60 seconds )
                          The lowest value is used. So if the user configures a lower limit in VictronConnect you cannot raise the level above this limit

/ErrorCode             <- 0=No Error
/FroniusDeviceType     <- Fronius specific product id list
/Position              <- 0=AC input 1; 1=AC output; 2=AC input 2
/PositionIsAdjustable  <- 0=Position is not adjustable; 1=Position is adjustable (optional)
/StatusCode            <- 0=Startup 0; 1=Startup 1; 2=Startup 2; 3=Startup
                          3; 4=Startup 4; 5=Startup 5; 6=Startup 6; 7=Running;
                          8=Standby; 9=Boot loading; 10=Error
/IsGenericEnergyMeter  <- PV inverter service is provided by a generic energy meter
                          (no power limiting available)
```


## AC chargers
```
com.victronenergy.charger

/Ac/In/L1/I            <- A AC
/Ac/In/L1/P            <- W
/Ac/In/CurrentLimit    <- A AC

/NrOfOutputs           <- The actual number of outputs.
/Dc/0/Voltage          <- V DC
/Dc/0/Current          <- A DC
/Dc/0/Temperature      <- °C - Battery temperature
/Dc/1/...              <- Same as /Dc/0/...
/Dc/2/...              <- Same as /Dc/0/...

/State                 <- 0=Off
                          2=Fault
                          3=Bulk
                          4=Absorption
                          5=Float
                          6=Storage
                          7=Equalize (manual)
                          11=Power supply mode
                          246=Repeated absorption
                          247=Auto equalize/Recondition
                          248=BatterySafe
/Mode                  <- 1=On; 4=Off
/ErrorCode             <- 0=No error 
                          1=Battery temperature too high
                          2=Battery voltage too high
                          3=Battery temperature sensor miswired (+)
                          4=Battery temperature sensor miswired (-)
                          5=Battery temperature sensor disconnected
                          6=Battery voltage sense miswired (+)
                          7=Battery voltage sense miswired (-)
                          8=Battery voltage sense disconnected
                          9=Battery voltage wire losses too high
                          17=Charger temperature too high
                          18=Charger over-current
                          20=Bulk time limit reached
                          34=Internal error
                          37=No input voltage
                          65=Device disappeared during parallel operation 
                          66=Incompatible device encountered for parallel operation 
                          67=BMS connection lost 
                          113=Internal error
                          114=Internal error
                          115=Communication lost
                          116=Internal error
                          117=Internal error
                          118=Internal error
                          119=Settings invalid/corrupted
                          120=Internal reference voltage failure
/Relay/0/State         <- 0=Disengaged; 1=Engaged. For most chargers this path is either not available, or
                          read only. Only the relay in Phoenix Smart Chargers is remote controllable. To be
                          able to do that, use VictronConnect to set the Relay Mode to remote control.
                          Note that its use is limited: the relay is only powered (and thus
                          only controllable) when the charger is switched on. It doesn't work when it's
                          turned off with AC connected.
                          More information also here: https://www.victronenergy.com/live/venus-os:large#controlling_relays
/Alarms/LowVoltage     <- 0=Inactive; 1=Active
/Alarms/HighVoltage    <- 0=Inactive; 1=Active
```

## Grid (and acload and genset) meter
```
com.victronenergy.grid
com.victronenergy.acload (when used as consumer to measure an acload)
com.victronenergy.genset (when used as producer to measure a genset)

/Ac/Energy/Forward     <- kWh  - bought energy (total of all phases)
/Ac/Energy/Reverse     <- kWh  - sold energy (total of all phases)
/Ac/Power              <- W    - total of all phases, real power
/Ac/PowerFactor        <-      - total power factor

/Ac/Current            <- A AC - Deprecated
/Ac/Voltage            <- V AC - Deprecated

/Ac/L1/Current         <- A AC
/Ac/L1/Energy/Forward  <- kWh  - bought
/Ac/L1/Energy/Reverse  <- kWh  - sold
/Ac/L1/Power           <- W, real power
/Ac/L1/PowerFactor     <- power factor
/Ac/L1/Voltage         <- V AC
/Ac/L2/*               <- same as L1
/Ac/L3/*               <- same as L1
/DeviceType
/ErrorCode

/IsGenericEnergyMeter  <- When an energy meter masquarades as a genset or acload, this is set to 1.
```

## Temperatures

These measurements originate from either the built-in wired temperature inputs on the GX device (Cerbo GX and Venus GX), or the wireless sensors made by Ruuvi.
```
com.victronenergy.temperature

/Temperature        degrees Celcius
/TemperatureType    0=battery; 1=fridge; 2=generic, 3=Room, 4=Outdoor, 5=WaterHeater, 6=Freezer
/CustomName

Wired inputs only:
/Status             0=Ok; 1=Disconnected; 2=Short circuited; 3=Reverse polarity; 4=Unknown
/Scale              <- normally not necessary! devices should be calibrated.
/Offset             <- normally not necessary! devices should be calibrated.

Ruuvis only:
/AccelX
/AccelY
/AccelZ
/BatteryVoltage     <- Sensor battery voltage
/Humidity           <- example: 62.9275016784668
/Pressure           <- example: 102.10400390625
/SeqNo              <- 17640
/TxPower            <- example: 4.0

Ruuvi Air only:
/PM25               <- PM2.5 particulate matter concentration in µg/m³ (range: 0-1000.0)
/CO2                <- CO₂ concentration in ppm (range: 0-40000)
/VOC                <- Volatile Organic Compounds index (unitless, 100 = average) (range: 0-500)
                       For VOC the index average is 100, i.e. values under 100 mean the air quality is improving
                       and values over 100 mean the air quality is getting worse.
/NOX                <- Nitrogen Oxides index (unitless, 1 = baseline) (range: 0-500)
                       Nox index has base value of 1, values higher than 1 meaning there's more nitrogen oxides in
                       the air than usual.
/Flags              <- Status flag (bit 0: calibration in progress)

Warning! We might still remove or dampen some of the above extra paths. While they are nice, for us they're only nice to have. And they create a load on the system since they update regularly, especially SeqNo and the Accelx,y,z. And then with for example 5 sensors its suddenly quite the extra load; reducing maximum number of installable solar chargers, for example.
```

## Meteo

```
com.victronenergy.meteo

/CellTemperature.     <-- Internal Panel temperature in Celsius
/ExternalTemperature  <-- External temperature in Celsius
/ErrorCode            <-- Bitwise ve reg warnings / alarms
/Irradiance           <-- Current irradiance in W/m2
/TodaysYield          <-- The yield that was recorded for today (since sunrise) in kWh
                          Calculated based on the set capacity of the system (via VictronConnect)
/WindDirection        <-- The wind direction in degrees (0-360)
/WindSpeed            <-- The wind speed in m/s
```

## Tank levels
```
com.victronenergy.tank

GENERIC
/Level              0 to 100%
/Remaining          m3
/Status             0=Ok; 1=Disconnected; 2=Short circuited; 3=Unknown; 4=Configuration error
/Capacity           m3
/FluidType          0=Fuel; 1=Fresh water; 2=Waste water; 3=Live well; 4=Oil; 5=Black water (sewage)
                    6=Gasoline; 7=Diesel; 8=Liquid  Petroleum Gas (LPG); 9=Liquid Natural Gas (LNG)
                    10=Hydraulic oil; 11=Raw water
                    This Fluidtype enumeration is kept in sync with NMEA2000 definitions.
/Standard           0=European (resistive); 1=USA (resistive); 2=Not applicable (used for Voltage and Amp sensors)


ALARMS
Note that these are not supported on all tanks, for example for N2K-connected tanks it doesnt
work, while for GX Tank, as well as built-in tank inputs in Cerbo GX & Venus GX it does.

/Alarms/High/Active       <-- configuration: the activate level. For example 10%
/Alarms/High/Delay        <-- configuration: delay in seconds
/Alarms/High/Enable       <-- configuration: enable/disable alarm switch
/Alarms/High/Restore      <-- configuration: the restore level, ie the hysterises. For example 15%.
/Alarms/High/State        <-- alarm state: DBUS-INVALID when the alarm is disabled; otherwise either 1 or 0.
/Alarms/Low/*             <-- same as above

OTHER
Same note. Not available for N2K connected tanks. Battery voltage and temperature are only available for Mopeka sensors
/BatteryVoltage
/FilterLength            <-- averaging filter, probably in seconds - to find out, compare with UI.
/RawUnit                 <-- can be V, and probably also mA and R or O.
/RawValue
/RawValueEmpty
/RawValueFull
/Shape                   <-- shape configuration (?)
/Temperature
```

## Pulse meters and digital inputs
See https://github.com/victronenergy/dbus-digitalinputs/blob/master/README.md#running

## Generator data
The below paths apply to Fischer Panda, ComAp and Hatz generators. Other generators should have similar data, but may not have all the same values. As support for more generators is implemented, this will be extended.

For more information about the Fischer Panda integration, see the [Venus & Fischer Panda manual](https://www.victronenergy.com/live/ccgx:fischer_panda).

For more information about ComAp integration, see the comap module in [dbus-modbus-client](https://github.com/victronenergy/dbus-modbus-client/).

Note that the data from the generator, and the more generic start/stop module are two different things and also have two different D-Bus paths:

1. com.victronenergy.(dc)genset   -> used for generator data, like voltages, RPM, oil pressure etcetera.
2. com.victronenergy.generator   -> start/stop code in Venus OS. Can activate a relay, but also, in case of Fischer panda, a generator directly via D-Bus.

```
com.victronenergy.genset
com.victronenergy.dcgenset

Populated for AC generators:
/Ac/Energy/Forward     <- kWh  - total energy produced by genset (optional)
/Ac/Power              <- W    - total of all phases, real power
/Ac/Frequency          <- Hz

/Ac/L1/Current         <- A AC
/Ac/L1/Power           <- W, real power
/Ac/L1/Voltage         <- V AC
/Ac/L2/*               <- same as L1
/Ac/L3/*               <- same as L1

/NrOfPhases            <- 1, 2 or 3

Populated for DC generators, i.e. Fischer Panda AGT and Hatz:
/Dc/0/Voltage               <- DC output voltage, V
/Dc/0/Current               <- DC output current, A
/HeatsinkTemperature        <- °C
/History/EnergyOut          <- (Optional) Total energy generated

/RemoteStartModeEnabled     <- 0=Disabled; 1=Enabled (read-only) (Was `AutoStart` in Venus 3.40 and earlier)
                               Needs to be 1 in order to start generator using the /Start path.
                               For Fischer Panda the remote start mode feature can only be enabled from fpControl panel.
/EnableRemoteStartMode      <- (Optional) Engage genset controller mode, which enables remote start/stop; Write 1 to enable
                               The path is only available for genset controllers, that support that functionality.

/Error/0/Id                 <- ""=No error (see error codes section on the top of this page for more details)
                               "fischerpanda:e-": Fischer Panda error codes
                               "dse:e-": DSE error codes
                               "hatz:[we]-": Hatz warning/error codes
/ModuleId                   <- Internal Fischer Panda module Id
/Start                      <- Start genset; 0=Stop; 1=Start; /RemoteStartModeEnabled must be 1
                               Note that the /Start item is controlled by the generator start/stop service as
                               long as /RemoteStartModeEnabled is set to 1. Manually starting/stopping the generator needs 
                               to be done by writing to com.victronenergy.generator.startstop1/ManualStart.
/StarterVoltage             <- Starter battery voltage
/StatusCode                 <- 0=Standby; 1..7=Startup; 8=Running; 9=Stopping; 10=Error

/Engine/CoolantTemperature  <- °C
/Engine/ExaustTemperature   <- °C
/Engine/Load                <- 0 to 100%
/Engine/OilPressure         <- kPa
/Engine/OilTemperature      <- °C
/Engine/OperatingHours      <- in seconds
/Engine/Speed               <- rpm
/Engine/WindingTemperature  <- °C
/Engine/Starts              <- absolute count  
```

## Generator start/stop

Presently two types of generator start/stop services are supported.
- Relay 1 on a GX device
- Multiple models & types of connected gensets, both AC and DC gensets.
  - ComAp
  - CRE
  - DEIF
  - DSE
  - Fischer Panda
  - Hatz

There can be multiple start/stop services. The service name starts with `com.victronenergy.generator`, and the fourth component will be `startstop0, startstop1` and so forth. Do not rely on the fourth component of the dbus name to identify the service. Most systems will only have one start/stop service, depending on whether the relay of the GX-device is used, or a FischerPanda generator is available on the CAN-bus.

The following paths apply to generator start/stop services:
```
com.victronenergy.generator

/Alarms/NoGeneratorAtAcIn       <- If configured for it, the alarm will be triggered if the generator 
                                         is not detected at the Multi/Quattro AC Input. 
                                         0 = No alarm, 2 = Alarm
/Alarms/NoGeneratorAtDcIn       <- Only for DC gensets. if configured for it, the alarm will be triggered if the current supplied by the DC 
                                         genset has not reached at least 5A within the first 5 minutes after starting.
                                         0 = No alarm, 2 = Alarm
/Alarms/AutoStartDisabled       <- Autostart alarm is armed, but autostart is disabled: 0 = OK; 2 = Alarm
                                   (this could happen if after service autostart is not re-enabled)
/Alarms/ServiceIntervalExceeded <- The generator is in need of a service: 0 = OK; 1 = Service required.
/AutoStartEnabled               <- 0 = Auto stop/start disabled; 1 = Auto stop-start enabled
/DigitalInput/Input             <- The digital input number that is signalling the startstop instance that the generator is running. 0 if no 
                                   digital input is configured.
/DigitalInput/Running           <- 0 / 1: The generator is not running / running according to the digital input.
/Enabled                        <- 0 = Generator start/stop disabled; 1 = Generator start/stop enabled. Generator start/stop will only be 
                                   disabled if there is a connected genset which requires a helper relay but the helper relay is not 
                                   configured.
/Error                          <- 0 = No error, 1 = Remote control disabled, 2 = Remote in fault condition
/GensetService                  <- The genset service that this startstop instance is controlling
/GensetServiceType              <- The type of genset service that this startstop instance is controlling: "genset" or "dcgenset"
/ManualStart                    <- Generator manual start. 0 = Stop, 1 = Start
/ManualStartTimer               <- Set it before a manual start to make the generator run for a fixed
                                         amount of seconds. Once the generator is started it indicates the
                                         seconds left until the generator is stopped.
/NextTestRun                    <- Seconds until the next periodic test run
/QuietHours                     <- Indicates if in quiet hours period.
                                         0 = Not in quiet hours, 1 = Quiet hours
/RunningByCondition             <- Condition that started or is keeping the generator running.
                                         Values = soc, acload, batterycurrent, batteryvoltage, inverterhightemp,
                                         inverteroverload, testrun, lossofcomunication, manual
/RunningByConditionCode         <- Same as `RunningByCondition` but in numeric codes. Stopped = 0,
                                         Manual = 1, TestRun = 2, LossOfCommunication = 3, Soc = 4, Acload = 5,
                                         BatteryCurrent = 6, BatteryVoltage = 7, InverterHighTemp = 8, InverterOverload = 9
/Runtime                        <- Seconds that the generator is running since it started. After one minute of runtime it updates
                               once per minute.
/SkipTestRun                    <- Indicates if the next test run will be skipped because it is not necessary
/State                          <- 0=Stopped; 1=Running; 2=Warm-up; 3=Cool-down;4=Stopping; 10=Error
/ServiceCounter                 <- Time left in hours, until service is required; Negative if service is overdue.
/ServiceCounterReset            <- Write 1 to reset the service counter.
/TestRunIntervalRuntime         <- Run time since last test run (seconds)
/TodayRuntime                   <- Today's run time (seconds)
/Type                           <- 0=Generic relay switched, 1=Fischer Panda (more may follow in future).
```
## vecan-xxx

Vecan-dbus makes a com.victronenergy.vecan service. It can be used to (a) see the list of devices found on the canbus (NMT) and update for example their instances. Also (b) the service provides paths that can be used to broadcast data onto the canbus:

Broadcast paths:
```
Single shot (per v2.80~32 or later):
/Link/Soc
/Link/TemperatureSense
/Link/VoltageSense
/Link/BatteryCurrent
/Link/ExtraBatteryCurrent

Repeated on interval with time-out:
/Link/ChargeVoltage     <—- part of ESS
/Link/NetworkMode
```

Above paths are being written to by Systemcalc. They’re part of ESS and DVCC.

Note for the above broadcast-paths: the device instance as configured for the gx device is used. And that instance is used by the solar chargers and other devices on the bus to either ignore or use such broadcasted data.

## alternator-and-dcsource

Alternators can be a digital interface to an alternator controller; such as the Wakespeed WS500 and Arco Zeus controllers. They can also be an OrionXS DC/DC charger. And otherwise a Victron SmartShunt configured to be an energy meter rather than a battery monitor.

```
alternator is com.victronenergy.alternator
dcsource is com.victronenergy.dcsource

/Dc/0/Voltage                <- V DC
/Dc/0/Current                <- A, positive when alternator is charging
/Dc/0/Temperature            <- Degrees centigrade, alternator temperature reading, or temperature sensor on SmarShunt/BMV (not available for OrionXS)
/Dc/1/Voltage                <- SmartShunt/BMV secondary battery voltage (if configured)

DC meter:
/Settings/MonitorMode        <- Specifies type of DC source
                                -1=Generic Source
                                -2=AC Charger
                                -3=DC/DC Charger
                                -4=Water Generator
                                -7=Shaft Generator
                                -8=Wind Charger
/History/EnergyOut           <- Total energy generated by Alternator
/Alarms/LowVoltage           <- Low voltage alarm
/Alarms/HighVoltage          <- High voltage alarm
/Alarms/LowStarterVoltage    <- Low voltage secondary battery
/Alarms/HighStarterVoltage   <- High voltage secondary battery
/Alarms/LowTemperature       <- Low temperature alarm
/Alarms/HighTemperature      <- High temperature alarm

Wakespeed WS500/Arco Zeus:
/Engine/Speed                <- Engine RPN
/FieldDrive                  <- Current limit in %
/Speed                       <- Alternator RPM
/State                       <- 0=Off
                                2=Fault
                                3=Bulk
                                4=Absorption
                                5=Float
                                6=Storage
                                7=Equalize
                                252=External control

OrionXS:
/Capabilities/Capabilities1
/Dc/0/Power                  <- Battery power
/Dc/In/V                     <- Input voltage
/Dc/In/I                     <- Input current
/Dc/In/P                     <- Input power
/DeviceOffReason             <- Reason why device is off; See solar charger section
/ErrorCode                   <- Error code; See solar charger section
/History/*                   <- Contains information about the charging cycles
/Link/BatteryCurrent         <- When SCS is enabled on the GX device, the battery current is written here to improve tail-current detection
/Link/ChargeCurrent          <- Charge current limit. Must be written every 60 seconds. Used if a managed battery or user defines a current limit.
/Link/ChargeVoltage          <- Charge voltage sent by a managed battery is written here
/Link/CurrentSenseActive     <- Indicates whether current sense is active
/Link/NetworkMode            <- Bitmask
                                0x1 = External control
                                0x4 = External voltage/current control
                                0x8 = Controled by BMS (causes Error #67, BMS lost, if external control is interrupted).
/Link/NetworkStatus          <- Bitmask
                                0x01 = Slave
                                0x02 = Master
                                0x04 = Standalone
                                0x20 = Using I-sense (/Link/BatteryCurrent)
                                0x40 = Using T-sense (/Link/TemperatureSense)
                                0x80 = Using V-sense (/Link/VoltageSense)
/Link/TemperatureSense       <- When STS is enabled, the battery temperature is written here
/Link/TemperatureSenseActive <- indicates when STS is in use
/Link/VoltageSense           <- When SVS is used, or when ESS is used, voltage sensed by the battery/multi is written here.
/Link/VoltageSenseActive     <- SVS is in use
/Mode                        <- 1=On; 4=Off
/Settings/BmsPresent         <- A bms is controlling the DCDC charger; This enables automatically if NetworkMode indicates BMS is present.
/Settings/DeviceFunction     <- 0=Charger(=Alternator), 1=PSU(=dcdc)
/Settings/ChargeCurrentLimit <- Maximum configured charge current of controller.
/Settings/OutputBattery      <- 0=main battery, 1=aux battery (will always be 0 for .alternator)
/State                       <- 0=Off
                                2=Fault
                                3=Bulk
                                4=Absorption
                                5=Float
                                6=Storage
                                7=Equalize
                              252=External control
```


## fuelcell

```
fuelcell is com.victronenergy.fuelcell

/Dc/0/Voltage              <-- V DC
/Dc/0/Current              <-- A, positive when fuel cell is generating power
/Dc/0/Temperature          <-- Degrees centigrade, temperature sensor on SmarShunt/BMV
/Dc/1/Voltage              <-- SmartShunt/BMV secondary battery voltage (if configured)
/History/EnergyOut         <-- Total energy generated by Fuel cell
/Alarms/LowVoltage         <-- Low voltage alarm
/Alarms/HighVoltage        <-- High voltage alarm
/Alarms/LowStarterVoltage  <-- Low voltage secondary battery (if configured)
/Alarms/HighStarterVoltage <-- High voltage secondary battery (if configured)
/Alarms/LowTemperature     <-- Low temperature alarm
/Alarms/HighTemperature    <-- High temperature alarm
```

## motordrive

```
This section defines the new N2K based motor drive paths, however com.victronenergy.motordrive has 
existed for a while although not very common, there is an existing profile, see vrmlogger datalist.py 
for example. Also DC meters, like the SmartShunt, configured to DC meter type "Electric Drive" 
uses com.victronenergy.motordrive.

/Dc/0/Voltage              <-- V DC
/Dc/0/Current              <-- A, can be positive and also negative, depending on if regeneration works.
/Dc/0/Power                <-- W, can be positive and also negative, depending on if regeneration works.
/Dc/0/Temperature          <-- Temperature of the motor or controller (optional)

/Controller/Temperature    <-- Temperature as reported by the controller (optional)
/Coolant/Temperature       <-- Temperature of the coolant (optional)
/Motor/Temperature         <-- Temperature as reported by the motor (optional)
/Motor/RPM                 <-- Motor speed (optional)
/Motor/Direction           <-- Direction the motor is spinning: 0=neutral, 1=reverse, 2=forward (optional)
```


## dcsystem

```
dcsystem is com.victronenergy.dcsystem

/Dc/0/Voltage              <-- V DC
/Dc/0/Current              <-- A, positive when power is consumed by DC loads, if there are chargers in your dcsystem
/Dc/0/Temperature          <-- Degrees centigrade, temperature sensor on SmarShunt/BMV
/Dc/1/Voltage              <-- SmartShunt/BMV secondary battery voltage (if configured)
/History/EnergyOut         <-- Total energy generated by dcsystem
/History/EnergyIn          <-- Total energy consumed by dcsystem
/Alarms/LowVoltage         <-- Low voltage alarm
/Alarms/HighVoltage        <-- High voltage alarm
/Alarms/LowStarterVoltage  <-- Low voltage secondary battery (if configured)
/Alarms/HighStarterVoltage <-- High voltage secondary battery (if configured)
/Alarms/LowTemperature     <-- Low temperature alarm
/Alarms/HighTemperature    <-- High temperature alarm
```

## dcload

```
com.victronenergy.dcload


/Dc/0/Voltage              <-- V DC
/Dc/0/Current              <-- A, positive when power is consumed by DC loads
/Dc/0/Temperature          <-- Degrees centigrade, temperature sensor on SmarShunt/BMV
/Dc/1/Voltage              <-- SmartShunt/BMV secondary battery voltage (if configured)
/History/EnergyIn          <-- Total energy consumed by dc load(s).
/Alarms/LowVoltage         <-- Low voltage alarm
/Alarms/HighVoltage        <-- High voltage alarm
/Alarms/LowStarterVoltage  <-- Low voltage secondary battery (if configured)
/Alarms/HighStarterVoltage <-- High voltage secondary battery (if configured)
/Alarms/LowTemperature     <-- Low temperature alarm
/Alarms/HighTemperature    <-- High temperature alarm
/Settings/MonitorMode      <-- Specifies type of DC load
                                1=Generic load
                                2=Electric Drive
                                3=Fridge
                                4=Water Pump
                                5=Bilge Pump
                                6=DC System
                                7=Inverter
                                8=Water Heater
```

## evcharger

```
com.victronenergy.evcharger

/Ac/Energy/Forward         <-- Total energy (kWh)
/Ac/L1/Power               <-- L1 Power used (W)
/Ac/L2/Power               <-- L2 Power used (W) 
/Ac/L3/Power               <-- L3 Power used (W)
/Ac/Power                  <-- AC Power (W)
/AutoStart                 <-- 0=Charger autostart disabled
                               1=Charger autostart enabled
/ChargingTime              <-- Session charging time (seconds) - DEPRECATED
/Session/Time              <-- Session charging time (seconds)
/Session/Energy            <-- Session charging energy (kWh)
/Session/Cost              <-- Session cost (no currency)
/Session/SavedCost         <-- Optional: Session saved cost (no currency)
/Connected                 <-- 
/Current                   <-- Actual charging current setpoint (A) calculated by the EVCS. This value can be lower than `/SetCurrent` 
                               due to limitations such as overload / overheating protection or max EV cable current. If there are no 
                               limitations, this value will be equal to `/SetCurrent`.
/EnableDisplay             <-- Control via display
                               0=control disabled, 1=control enabled
/MaxCurrent                <-- The maximum current (A) the EVCS is allowed to charge the EV with. This is an installer setting, not to be 
                               used for any dynamic control loops.
/Mode                      <-- 0=Manual
                               1=Auto
/Model                     <-- Model, e.g. AC22E or AC22NS (for No Screen)
/Position                  <-- 0=AC Output, 1=AC Input
/PositionIsAdjustable      <-- 0=Position is not adjustable, 1=Position is adjustable (optional)
/Role                      <-- 
/SetCurrent                <-- Charge current setpoint (A). The current setpoint can only be controlled in "Manual" mode. 
                               This path corresponds to the slider on the LCD screen of the EVCS (for the model with LCD).
/StartStop                 <-- Starting and stopping charging sessions, will be automatically engaged if /AutoStart is 1
/Status                    <-- 0=disconnected, 1=connected, 2=charging, 3=charged,
                               4=waiting for sun, 5=waiting for RFID, 6=waiting for start,
                               7=low SOC, 8=ground test error, 9=welded contacts error,
                               10=CP input test error (shorted), 11=residual current detected,
                               12=undervoltage detected, 13=overvoltage detected,
                               14=overheating detected, 15-19=reserved,
                               20=charging limit
/IsGenericEnergyMeter      <-- The device measuring the EVSE is a generic energy meter (lacks 
                               EVSE specific functions such as StartStop)
```

## Heatpump
**Note: This service is under development.**
```
/State             -> State of heat pump (enum to be decided later)
/Temperature       -> Current water temperature (optional if no temperature reading available)
/TargetTemperature -> Target water temperature (optional if not available)
/Ac/Power          -> Power currently consumed
/Ac/Energy/Forward -> Total energy consumed
/Position
```


## switch
Intially developed for the Victron GX IO Extender, Node-RED virtual switch, as well as Energy Solutions (ES) DC Smart Switch, this API is the basis for controlling lights, providing flexible controls for automation, and other outputs using Venus OS.

Note that the interface here is listed under com.victronenergy.switch, which is the D-Bus service name to be used for dedicated switching hardware. However, any service that has a switchable output available for users to control can list them with the same API under their service. The GUI scans all services for `/SwitchableOutput/x/..` entries, and will list the configuration in a separate menu in the device page, and the switches in the switching pane.


For example:
- `com.victronenergy.acload.shelly_<sn> /SwitchableOutput/..` 
- `com.victronenergy.solarcharger /SwitchableOutput/..`
- `com.victronenergy.multi /SwitchableOutput/..`
- and so forth.

```
com.victronenergy.switch

Generic:
/State          <-- Current state of the whole module. Visible in the UI in the Device List -> 
                    SmartSwitch -> Settings. Not visible on the switch card, also not necessary
                    because in case of a module level problem, all channels will indicate disabled.
                    Values offset by 0x100 to allow common state component in QML
                    0x100 = Connected
                    0x101 = Over temperature
                    0x102 = Temperature warning
                    0x103 = Channel fault
                    0x104 = Channel Tripped
                    0x105 = Under Voltage


OPERATIONAL PATHS PER CHANNEL:
Note that <x> should be a clear label of the output channel, not necessarily an integer. 
<x> can be used in the UI to display the output when /SwitchableOutput/x/Settings/CustomName 
is not set or not valid.

/SwitchableOutput/x/State             <-- RW (optional) / Requested on/off state of channel, separate from dimming.
                                          In rare cases, state can be absent/invalid. If this is the case, the 
                                          UI element in the switch pane should not be shown.
/SwitchableOutput/x/Dimming           <-- RW (optional) / 0 to 100%, read/write.
                                          Optional: required only for dimmable outputs, otherwise invalid or
                                          doesn't exist. 
/SwitchableOutput/x/LightControls     <-- RW (optional) 
                                          Used for multi-channel dimmers (types 11, 12, 13), this is 
                                          an array of double with the following values:
                                          0 | Hue               | 0 - 360 degrees
                                          1 | Saturation        | 0 - 100 %
                                          2 | Brightness        | 0 - 100 %
                                          3 | White             | 0 - 100 %
                                          4 | Color temperature | 0 - 6500 K
                                          Producers should change the parameters relevant for their type (check /Type)
                                          Do not set the unused parameters to invalid or NULL.
/SwitchableOutput/x/Measurement       <-- R (optional) / Measured value of the actuator that is controlled by /Dimming. 
                                          e.g. for a temperature setpoint slider, /Dimming holds the setpoint value and
                                          /Measurement holds the measured temperature, if available.
                                          GUI will display the measured value if this path is populated. 
/SwitchableOutput/x/Name              <-- R / Channel default name, must be set by the driver and is not writable.
/SwitchableOutput/x/Status            <-- R / Channel status

                       Normal states, visible in the component itself:
                       0x00 = Off
                       0x09 = On <- OR-ed state of Active and Input Active.

                       Exceptional states visible in the component itself

                       0x02 = Tripped
                       0x04 = Over temperature

                       Exceptional states, made visible by a extra label in the UI:
                       0x01 = Powered <- Voltage present on the Channels supply in the case where the 
                                         channels are individually supplied or if not and channel output
                                         is being back fed. In latter case query if input/analog input 
                                         and if they go on dbus as com.victronenergy.digitalinput
                       0x08 = Output fault <- Generic output fault
                       0x10 = Short fault  <- A certain hardware error that the switch self-diagnoses (ES Smart switch specific)
                       0x20 = Disabled     <- The hardware indicates this status in case for some 
                                              reason the switch is disabled. For example in case
                                              the whole module is in over temperature.
                       0x40 = Bypassed     <- The switching circuit is bypassed, so the channel is permanently on.
                       0x80 = Ext. control <- The switching circuit is externally controlled and dimming/value might not be valid. 
                                              For example for a RGB light that is in sound mode, it is not needed to continuously update the color.
/SwitchableOutput/x/Auto           <-- RW (optional) Used by the three-state switch (9) and bilge pump control (10). 
                                       When set, the driver or another service will control `/State`, and 
                                       the user cannot control the state from the UI.
                                       0: Manual mode, user can control the output from the UI. (default)
                                       1: Auto mode, user cannot control the output from the UI.
/SwitchableOutput/x/Temperature    <-- R / temperature of the switch,
                                       Optional: not all output types will feature temp. measurement.
/SwitchableOutput/x/Voltage        <-- R / voltage of its output
                                       Optional: not all output types will feature voltage measurement.
/SwitchableOutput/x/Current        <-- R / the current in amps. optional
                                       Optional: not all output types will feature current measurement.


SETTINGS:
/SwitchableOutput/x/Settings/Group             <-- RW / max 32 bytes utf8 long string, free input, used by the 
                                                   UI to group switches with the same group name onto 
                                                   the same card. When left blank (dbus-invalid), the UI 
                                                   falls back to grouping them by dbus service.
/SwitchableOutput/x/Settings/CustomName        <-- RW / the label; max 32 bytes utf8 long string. Preferably stored on the device itself.
/SwitchableOutput/x/Settings/ShowUIControl     <-- RW / integer

                                                   (optional) Indicate if the control is shown in the local  and in the remote UI
                                                   If used, set to 1 by default.
                                                   (for usage in Node-RED, but not in the gui)

                                                   Values:
                                                   0bxx1: Show control in all UI's
                                                   0b000: Hide in all UI's
                                                   0b010: Show only in local UI's (GUI running natively on GX, MFD and WASM over local LAN)
                                                   0b100: Show only in remote UI's (VRM remote console and VRM switch pane)

/SwitchableOutput/x/Settings/Type              <-- RW / Specifies the output type:
                                                       0 = momentary
                                                       1 = toggle
                                                       2 = dimmable (pwm)
                                                       3 = Temperature setpoint
                                                       4 = Stepped switch
                                                       5 = Slave mode (ES Smartswitch only)
                                                       6 = Dropdown
                                                       7 = Basic slider
                                                       8 = Numeric input box
                                                       9 = Three-state switch
                                                       10 = Bilge pump control
                                                       11 = RGB color wheel
                                                       12 = CCT color wheel
                                                       13 = RGBW color wheel
                                                   Preferably stored on the device itself. 
                                                   The device should reset the output to its inactive state
                                                   when the type is changed to momentary to prevent the 
                                                   output being in the active state while the user is not 
                                                   pressing the button.
/SwitchableOutput/x/Settings/ValidTypes        <-- R / binary field where each bit corresponds to the 
                                                   enum of xx/type indicates which options the UI should 
                                                   provide to the user.

                                                   In case the output is not controllable, set /ValidTypes to 0 and invalidate /Type.
/SwitchableOutput/x/Settings/Function          <-- RW (optional) / Set the function of the digital output. The function is
                                                   currently only used with digital outputs (of type "toggle"),
                                                   so not with dimmable outputs.

                                                   Note that currently only the GX internal relays support
                                                   functions other than "Manual".
                                                   When the path is invalid or absent, the function is set to manual

                                                   0: Alarm
                                                   1: Generator start/stop
                                                   2: Manual, 
                                                   3: Tank pump
                                                   4: Temperature
                                                   5: Genset helper relay

                                                   ES SmartSwitch: only manual
                                                   GX: builtin relays all options, second relay at 
                                                   least manual, alarm (new) and temperature
                                                   IO extender: only manual
                                                   BMV, smartsolar, other: only manual 
                                                   
/SwitchableOutput/x/Settings/ValidFunctions    <-- R / binary field where each bit corresponds 
                                                   to the enum of xx/function indicates which options the UI 
                                                   should provide to the user.
/SwitchableOutput/x/Settings/FuseRating        <-- RW (optional) Channel trip rating in amps; 
                                                   Preferably stored on the device. 
                                                   GetMin and GetMax are implemented to get the limits.
/SwitchableOutput/x/Settings/DimmingMin        <-- RW (optional) Only used for dimmable outputs. Defines
                                                   the minimum dimvalue. 0 will be used if omitted.
/SwitchableOutput/x/Settings/DimmingMax        <-- RW (optional) Only used for dimmable outputs. Defines
                                                   the maximum dimvalue. 100 will be used if omitted.
/SwitchableOutput/x/Settings/StepSize          <-- RW (optional) Only used for dimmable outputs. Defines 
                                                   the stepsize of the output. If not present, 
                                                   a stepsize of 1 should be used.
/SwitchableOutput/x/Settings/Decimals          <-- RW (optional) Only used for dimmable outputs. Defines the number 
                                                   of decimals to use when the GUI cannot accurately determine 
                                                   it from the stepsize path. Set this to enforce the number of decimals.
/SwitchableOutput/x/Settings/Unit              <-- RW (optional) Text field with the unit to display.
                                                   Only applicable to the Basic Slider (7) and Numeric input (8).

                                                   There are three units configurable by the user in Venus OS:
                                                   Speed (Knots, km/h, ..), Temperature (Celcius, Fahrenheit),
                                                   Volume (Litres, m3, ... ).

                                                   To all switches/node-red and so forth systems to have controls
                                                   in the units that are configured system wide by the user, we
                                                   introduce special texts that the UI control will recognize
                                                   and when used it will use the user configured unit:

                                                   1. Speed: keyword: "/Speed", base unit: m/s
                                                   2. Temperature: keyword: "/Temperature", base unit: Degrees Celsius
                                                   3. Volume: keyword: "/Volume", base unit: m3

                                                   The data (dimming, min, max, stepsize, actual value) is then to
                                                   be sent in the corresponding base unit.

                                                   For other use cases, when its not wanted, then there is still the
                                                   freedom that we had: path is set to which ever string/unit, and
                                                   data is sent is in the same unit.

                                                   Note that the temperature slider is already doing this, and doesn't
                                                   have this Settings/Unit path.
/SwitchableOutput/x/Settings/Polarity          <-- RW (optional) Polarity of the output.
                                                     0: Active high / Normally open
                                                     1: Active low / Normally closed
/SwitchableOutput/x/Settings/StartupState      <-- RW (optional) Defines the state of the output when the 
                                                   device is powered on.

                                                   0: Output off
                                                   1: Output on
                                                   2: Restore from memory (default)
/SwitchableOutput/x/Settings/StartupDimming    <-- RW (optional) Defines the dim level of a dimmable output
                                                   when the device is powered on.

                                                   0-100: Fixed value to be written at startup
                                                   -1: Restore from memory (default)
/SwitchableOutput/x/Settings/StartupState          RW (optional): Defines the initial state of the output
                                                   0: off
                                                   1: on
                                                   -1: restore last state from memory
/SwitchableOutput/x/Settings/DimCurve              RW (optional): Defines the dimming curve
                                                   0: Linear
                                                   1: Optical
/SwitchableOutput/x/Settings/OutputLimitMin        RW (optional): Float value between 0 and 100%. 4
                                                   PWM duty-cycle corresponding to 0% dimlevel
/SwitchableOutput/x/Settings/OutputLimitMax        RW (optional): Float value between 0 and 100%. 
                                                   PWM duty-cycle corresponding to 100% dimlevel
/SwitchableOutput/x/Settings/FuseDetection     <-- RW (optional) Set fuse detection mode on the DC Distribution board
                                                   0: Disabled
                                                   1: Enabled
                                                   2: Only when the output is off
/SwitchableOutput/x/Settings/Labels            <-- RW (optional) Define the labels of the multi-option switch.
                                                   For a multi-option switch, the `min` of the `/Dimming` path must be 0.
                                                   The `max` of the `/Dimming` path then defines the number of options.
                                                   The `../Labels/` path defines the labels of the presented options 
                                                   as a string array:
                                                   ['Label 1','Label 2', 'Label 3']
                                                   



```

### Generic input API

**Under development**

To support all sorts of inputs (digital, analog, virtual, etc.) in the same structure as the switchable output API. This is used to display read-only values on the switching pane on the GX device.
Input devices (digital inputs, sensors, etc.) can report their values in this API so they can be shown in the switching pane. Similar to the Switchable Output API, the GUI will scan all services for /GenericInput/x entries

```
/GenericInput/x/Value                          <-- R: Value of the input. Can be an integer or a double or invalid.
                                                   This path can be invalid when the input is stateless but reports events.
                                                   If invalid, no UI element can be displayed in the switching pane.

/GenericInput/x/Event                          <-- R: Last event. Used by digital inputs that detect events. 
                                                   Supported events:
                                                   0: None
                                                   1: Single tap
                                                   Future expansion, e.g.:
                                                   2: Double tap
                                                   3: Swipe up
                                                      
                                                   The value of the path holds the event. When the same event is 
                                                   emitted repeatedly, the value will not change, but the service
                                                   will force-send an itemschanged dbus event.
                                                      
/GenericInput/x/Status                         <-- R: Status of the input / sensor
                                                   0x00: OK
                                                   0x01: Fault
                                                   0x02: Sensor battery low (Useful?)
/GenericInput/x/Name                       <-- R / Channel default name, must be set by the driver and is not writable.

/GenericInput/x/Settings/Group             <-- RW / max 32 bytes utf8 long string, free input, used by the 
                                                   UI to group switches with the same group name onto 
                                                   the same card. When left blank (dbus-invalid), the UI 
                                                   falls back to grouping them by dbus service.
/GenericInput/x/Settings/CustomName        <-- RW / the label; max 32 bytes utf8 long string. Preferably stored on the device itself.
/GenericInput/x/Settings/ShowUIIndicator   <-- RW / integer (optional) Indicate if the indicator 
                                                   is shown in the local  and in the remote UI
                                                   If used, set to 3 by default.
                                                   (for usage in Node-RED, but not in the gui)
 
                                                   0x00: Do not show the control item
                                                   0x01: Show in the local UI
                                                   0x02: Show in all remote UI's
                                                   0x03: Show in all UI's
/GenericInput/x/Settings/Type              <-- RW / Specifies the output type:
                                                   0: Boolean indicator
                                                   1: Discrete value indicator
                                                   2: Continuous value indicator without range
                                                   3: Continuous value indicator with range
                                                   4: Temperature indicator (with range)
/GenericInput/x/Settings/ValidTypes        <-- R / binary field where each bit corresponds to the 
                                                   enum of xx/type indicates which options the UI should 
                                                   provide to the user.

                                                   In case the output is not controllable, set /ValidTypes to 0 and invalidate /Type.
/GenericInput/x/Settings/Unit                  <-- RW (optional) Text field with the unit to display.
                                                   For the Discrete indicator, this holds a translation
                                                   from the discrete values to the labels to display.
                                                   Specify the labels corresponding to the values, separated with
                                                   the pipe symbol ('|') e.g. For a discrete indicator with 
                                                   two values 0, and 1, specify "off|on" to show "off" when the value is 0,
                                                   and "on" when the value is 1.

                                                   For the continuous value indicators, specify the unit directly, 
                                                   or a reserved keyword in order to use GX-wide unit for a 
                                                   quantity (see /SwitchableOutput/x/Settings/Unit)
/GenericInput/x/Settings/RangeMax              <-- R (optional) Specifies the maximum of the range, only used for types with a range.
/GenericInput/x/Settings/RangeMin              <-- R (optional) Specifies the minimum of the range, only used for types with a range.
/GenericInput/x/Settings/Decimals              <-- R (optional) Specifies the number of decimals to display a value in. 
                                                   Not used for the Discrete value indicator.
/GenericInput/x/Settings/Invert                <-- RW (optional) Invert the input. Only used for the discrete input type:
                                                   0: Normal
                                                   1: Inverted
/GenericInput/x/Settings/DigitalInputMode      <-- RW (optional) Specify the mode of the digital input:
                                                   0: Disabled
                                                   1: Digitalinput
                                                   2: Toggle switch
                                                   3: Press button
                                                   4: Press and hold button
```


## rvc-xxx

dbus-rv-c makes a com.victronenergy.rvc service. It can be used to see the list of devices found on the canbus (NMT) and update for example their instances.

```
com.victronenergy.rvc
/Alarms/SameUniqueNameUsed       <-- Indicates if the unique identifier from the GX is used by another device on the RV-C network. 

/Devices/#/ChargerInstance       <-- Charger instance used in CHARGER_* DGNs.
/Devices/#/InverterInstance      <-- Inverter instance used in INVERTER_* DGNs.
/Devices/#/Line/0/Instance       <-- Line #1 instance used in INVERTER_AC_STATUS_* and CHARGER_AC_STATUS_* DGNs.
                                     0=L1, 1=L2
/Devices/#/Line/1/Instance       <-- Line #2 instance used in INVERTER_AC_STATUS_* and CHARGER_AC_STATUS_* DGNs.
                                     0=L1, 1=L2
/Devices/#/DcSource/n/Instance   <-- DC source n instance used in DC_SOURCE_STATUS_* DGNs.
/Devices/#/DcSource/n/Priority   <-- DC source n priority used in DC_SOURCE_STATUS_* DGNs.
/Devices/#/TankInstance          <-- Tank instance used in TANK_STATUS DGN.
```

## platform

The `com.victronenergy.platform` dbus service is provided by [venus-platform](https://github.com/victronenergy/venus-platform).

One of the things it does is monitor all devices and other services for alarms, warnings, errors and other things that need to be notified to the user.

Its output is a structure on D-Bus of notifications.

This structure is picked from either D-Bus or MQTT by the different UIs.

At this moment, the VRM portal and its alarms/notifications service does not yet use this; but changing that over to this is under exploration.

Detailed documentation:

A notification can be active or no longer active (so for example the voltage is still too high or already recovered), as well as acknowledged or not acknowledged. Together this is a matrix and in total there are four possible combinations.

Different types of notifications:
```
1) Warning       -> example: battery voltage has dropped below a warning level
2) Alarm         -> example: battery voltage has dropped further, below the inverter
                    shutdown level. Inverter has shut down. When there is an alarm, the
                    device has always shut down.
3) Error         -> example: calibration lost; or settings lost. When there is an error, Device has always shut down.
4) Information   -> example: Information 66 - Incompatible device, from the mppt solar chargers.
5) Notification  -> example: firmware update available, on a GX.
                    note that this term is confusing since now we have a notification
                    center and a notification type.
```
**NOTE: The notification types "Error" and "Notification" are currently not supported by venus-platform.**

Errors vs Alarms:

It is difficult to differentiate between errors and alarms. Alarms are critical situations arising during operation of which the system may be able to recover with or without user intervention. Any parameter which is outside safe operational limits should trigger an alarm, like high voltage, high temperature, etc.

When something is broken or wrongly configured which prevents the system from operating, it should be classified as an error. This usually requires a technician or service engineer to be resolved. Examples are broken or disconnected hardware or cables, missing settings, missing calibrations, etc.

For attention drawing we have defined two levels:
1. High: UI switches automatically to the notification center + (when enabled) relay, or buzzer or both are engaged.
2. Low: an icon shows indicates to user that there are notifications.

dbus paths
```
com.victronenergy.platform
ModificationChecks/DataPartitionFreeSpace       <- Free data partition space in bytes
ModificationChecks/FsModifiedState              <- 0: Root FS was not modified
                                                   1: Root FS was modified
ModificationChecks/SshKeyForRootPresent         <- authorized_keys for root user present
ModificationChecks/StartCheck                   <- Send a 1 here to re-run the modification checks
ModificationChecks/SystemHooksState             <- Bit 1 (decimal 1): /data/rc.local.disabled present; venus-platform renames the
                                                   file to this name if
                                                   com.victronenergy.settings/Settings/System/ModificationChecks/AllModificationsEnabled
                                                   is set to 0 and back to rc.local if set to 1
                                                   Bit 2 (decimal 2): /data/rcS.local.disabled present; venus-platform renames the
                                                   file to this name if
                                                   com.victronenergy.settings/Settings/System/ModificationChecks/AllModificationsEnabled
                                                   is set to 0 and back to rc.local if set to 1
                                                   Bit 3 (decimal 4): /data/rc.local present
                                                   Bit 4 (decimal 8): /data/rcS.local present
                                                   Bit 5 (decimal 16): /run/venus/custom-rc present
Notifications/AcknowledgeAll                    <- Send a 1 in here to acknowledge all the not yet acknowledged alarms
Notifications/Alarm                             <- 0: Visual and audible attention drawing is not needed. All entries are 
                                                      either acknowledged or not of the type that requires audible attention.
                                                   1: Visual and audible attention drawing needed:
                                                      One of more of the notifications is an alarm that is active and not 
                                                      yet acknowledged. As long as this is the case, the buzzer/relay is 
                                                      activated (if enabled) and the GUI will automatically switch to 
                                                      the notifications page.
                                                      - gui-v2 uses this to know if it should show a certain icon to the user.
                                                      - venus-platform engages buzzer and/or relay if this path is active.
Notifications/Alert                             <- 0: Visual attention drawing not needed.
                                                   1: Visual attention drawing needed: 
                                                      One or more of the notifications is not acknowledged. Remains active 
                                                      until all notifications are acknowledged, even if the alarm/warning 
                                                      condition is not active anymore.
                                                      If 1, the GUI shows the flashing notification triangle. The 
                                                      buzzer/relay will not be engaged and the GUI does not switch
                                                      to the notification page based on this path.
Notifications/NumberOfActiveNotifications          <- Number of active notifications
Notifications/NumberOfNotifications                <- Number of total notifications
Notifications/NumberOfActiveAlarms                 <- Number of active alarms. Acknowledged or not.
Notifications/NumberOfActiveWarnings               <- Number of active warnings. Acknowledged or not.
Notifications/NumberOfActiveInformations           <- Number of active informations. Acknowledged or not.
Notifications/NumberOfUnAcknowledgedAlarms         <- Number of unacknowledged alarms. Active or not.
Notifications/NumberOfUnAcknowledgedWarnings       <- Number of unacknowledged warnings. Active or not.
Notifications/NumberOfUnAcknowledgedInformations   <- Number of unacknowledged informations. Active or not.
Notifications/[0-19]/Acknowledged                  <- Acknowledged status
                                                      0: not yet acknowledged
                                                      1: acknowledged
Notifications/[0-19]/Active                        <- Condition that triggered the notification is still active [1] or not [0] 
Notifications/[0-19]/AlarmValue                    <- Value of the alarm item/trigger
Notifications/[0-19]/Value                         <- Value that caused the alarm at the moment the it was triggered, for example,
                                                   the temperature on a high temperature alarm or the SOC on a low SOC alarm.
Notifications/[0-19]/DateTime                      <- Notification creation date and time
Notifications/[0-19]/Description                   <- Description of the alarm/notification, translated to the language selected 
                                                   in the GUI.
Notifications/[0-19]/Service                       <- D-Bus Service name of the product/service that triggered the notification
Notifications/[0-19]/Trigger                       <- D-Bus Path that triggered the notification
Notifications/[0-19]/Type                          <- Type of notification
                                                      0: Warning
                                                      1: Alarm
                                                      2: Notification  <- THIS ONE NEEDS RENAMING AND WHAT ABOUT ERRORS?
ProductName                                        <- Name of the product
Security/Api                                       <- Handles security-related configuration changes and processes a JSON input 
                                                      value to update the system's security settings.
```
### Networking
Venus-platform handles the networking of the GX and exposes paths for controlling and monitoring its interfaces

dbus paths
```
com.victronenergy.platform
Network/ConfigChanged                        <- Used by the security API to initiate a reconnect / re-authentication 
                                                when the security profile changes.
Network/Ethernet/LinkLocalIpAddress          <- Link local address of the ethernet interface
Network/HasBluetoothSupport                  <- 1: Bluetooth support, 0: No bluetooth support
Network/Services                             <- Available services on the ethernet and wifi interface.
                                                This is a JSON description. E.g.:
                                                {"ethernet":{"Wired":{<properties>}},"wifi":{<AP name>:{<properties>}}}
Network/SetValue                             <- Entry point to control the API. The value passed to this path is 
                                                the command to execute, in JSON. Used by the GUI to connect/disconnect 
                                                and change service properties.
Network/Wifi/Scan                            <- 1: Start wifi scan.
Network/Wifi/SignalStrength                  <- Normalized value of the wifi signal strength. Value is between 0 and 100.
                                                Will be set to 0 if the wifi service is not available at the time of fetching the strength.
Network/Wifi/State                           <- Wifi state: "ready", "online", "idle", "association" or "configuration"

```
### VE.Bus Backup&Restore

Venus-platform exposes an interface for backup and restore of VE.Bus settings. The actual backup and restore action is executed through mk2vsc.
 
Note: Backup files are VE.Bus firmware version specific and can only be used to restore settings on products with matching firmware versions.

dbus paths
```
com.victronenergy.platform
Vebus/Interface/tty##/Action                      <- Start backup/restore action
                                                     0: idle
                                                     1: backup
                                                     2: restore
                                                     3: delete backup file
Vebus/Interface/tty##/AvailableBackups            <- Lists available firmware compatible backup files in JSON format
                                                     ["MyQuatroNew-ttyS2.rvsc", "MyQuattroOld-ttyS2.rvsc"]
Vebus/Interface/tty##/Error                       <- mk2vsc error code 
                                                     30: MK2/MK3 communication error
                                                     31: Product address not reachable
                                                     32: Incompatible MK2 firmware version
                                                     33: No VE.Bus product was found
                                                     34: Too many devices on the VE.Bus
                                                     35: Timed out
                                                     36: Wrong password
                                                     40: Malloc error
                                                     45: Uploaded file does not contain settings data for the connected unit
                                                     46: Uploaded file does not match model and/or installed firmware version
                                                     47: More than one unknown unit detected
                                                     48: Updating a single unit with another unit's settings is not possible (Should not occur)
                                                     49: The number of units in file does not match the number of units discovered
                                                     50: File open error
                                                     51: File write error
                                                     52: File read error
                                                     53: File checksum error
                                                     54: File incompatible version number
                                                     55: File section not found
                                                     56: File format error
                                                     57: Product number does not match file
                                                     58: File expired
                                                     59: Wrong file format
                                                     60: VE.Bus write of assistant enable/disable setting failed
                                                     61: Incompatible VE.Bus system configuration. Writing system configuration failed
                                                     62: Cannot read settings. VE.Bus system not properly configured
                                                     70: Assistants write failed
                                                     71: Assistants read failed
                                                     72: Grid info read failed
                                                     100: OSerror, unknown application
                                                     201: Failed to open com port(no response)
Vebus/Interface/tty##/File                        <- File name for backup/restore
Vebus/Interface/tty##/FirmwareIncompatibleBackups <- List firmware incompatible backup files (Same format as AvailableBackups)
Vebus/Interface/tty##/Info                        <- mk2vsc status messages
                                                     10: init
                                                     11: query products
                                                     12: done
                                                     21: read setting data
                                                     22: read assistants
                                                     23: read vebus configuration
                                                     24: read grid info
                                                     30: write settings info
                                                     31: write settings data
                                                     32: write assistants
                                                     33: write vebus configuration
                                                     40: resetting vebus products
Vebus/Interface/ttyS2/Notify                     <-  Backup&Restore action result
                                                     1: backup successful
                                                     2: restore successful
                                                     3: file delete successful
                                                     101: backup process unexpedly closed
                                                     102: restore process unexpedly closed
                                                     103: file delete failed
```

## gps

[dbus-gps](https://github.com/victronenergy/dbus_gps) makes a `com.victronenergy.gps.vettyUSB1` service. It can be used to expose the position, speed and course of the GX device. Typically the information gets retrieved in the NMEA0183 format.

Also there is the vecan-dbus driver, which when found on  the N2K network, puts GPS data on dbus as com.victronenergy.gps services.

Note that dbus-systemcalc monitors the dbus for all gps services, and makes the most suitable one available under `/GpsService` and `/GpsSpeed`.
Details of that are in [/delegates/gps.py](https://github.com/victronenergy/dbus-systemcalc-py/blob/master/delegates/gps.py).

```
com.victronenergy.gps
Altitude                        <- The height in meters
Course                          <- The direction the de device is going in degrees
Fix                             <- If the gps can determine its position. 0: no fix, 1: fix
NrOfSatellites                  <- The number of satellites in view
Position/Latitude               <- The latitude in degrees
Position/Longitude              <- The longitude in degrees
Speed                           <- The speed the device is traveling in, in m/s
```

## ble

[dbus-ble-sensors](https://github.com/victronenergy/dbus-ble-sensors) provides the `com.victronenergy.ble` service, indicating the used hardware and found BLE devices.

Typically the found BLE device will also create a [temperature](#temperature), [meteo](#meteo) or [tank](#tank) service, containing the sensor data.

```
com.victronenergy.ble

ContinuousScan                  <- Should the system scan for BLE devices continuously

The X contains the device type (e.g. ruuvi_ or solarsense_) prepended with the hardware address.
Devices/X/Enabled               <- If advertisements of the devices are propagated into the seperate service
Devices/X/Name                  <- The custom name of the found BLE sensor

Interfaces/hci[0-9]/Address     <- The MAC address of the bluetooth interface

```

