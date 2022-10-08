# followthegreen
Follow the green, an X-Plane ATC A-SMGCS experience (Originally from devleaks)

Additions by Gunduran (Detlev Hoffmann)

Recent changes:
* Is working for XP12 - Repsecting the *Global Scenery* Folder
* Is loading asynchronously using a separate process (Working for Follow the green and Show Taxiways)
* Now using the airport data to respect the Taxiway conditions. 
  If in the apt.dat taxiways are classified with ICAO Airdome Reference Codes (A-F), it will be mapped against the Airplane ICAO code. 
  The list of Airplane codes comes from the FAA and there is a small step of mapping the FAA Aircaft Design Group to the Airdome Reference Code embedded.

Ideas:
* Load of Airport Data in a separate process ==> Done, main dialog shows loading until the load is finished, need some more testing for airports without taxiways etc.
  
* Move from the old style windows to the new styles (also dragable outside x-plane frame) and list all the destinations in combination with typing the first digits

* draw a map of the taxiways and destinations and make it click / selectable 

* Enter ATC routing information (e.g. you've landed in EDDK on 14L and exited via A3 and want to go to B12, ATC might advise me to use E A5 B or A B
  this should be done using a scratchpad where you start entering by keyboard the first possible digits (in the example above if you stand A3 and you enter E it will be 
  then A4 or A5 possible or if you enter A it will be B (perhaps also A4 E A5) 
