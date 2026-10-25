extends RefCounted
## Tunable GAME damage, not a calibrated wound or ammunition simulator.
## Momentum for the existing exaggerated knockback is intentionally separate.
const PROFILES := [
	{"name":"Pistol","mass_kg":0.008,"speed_mps":350.0,"pellets":1,"interval":0.22,"deposit":0.38},
	{"name":".44 game profile","mass_kg":0.0156,"speed_mps":420.0,"pellets":1,"interval":0.32,"deposit":0.65},
	{"name":"Buckshot","mass_kg":0.0035,"speed_mps":360.0,"pellets":8,"interval":0.55,"deposit":0.65},
	{"name":"Automatic rifle","mass_kg":0.004,"speed_mps":800.0,"pellets":1,"interval":0.10,"deposit":0.42}]
const JOULES_PER_CM3 := 2.5
static func projectile(profile: int, multiplier := 1.0) -> Dictionary:
	var p: Dictionary=PROFILES[clampi(profile,0,PROFILES.size()-1)]
	var energy: float=0.5*p.mass_kg*p.speed_mps*p.speed_mps
	return {"energy_j":energy,"deposited_j":energy*p.deposit,
		"volume_m3":energy*p.deposit/JOULES_PER_CM3*0.000001*maxf(multiplier,0.0),"profile":profile}
static func channel_radius(volume: float, length: float) -> float:
	return clampf(sqrt(maxf(0.0,volume)/(PI*maxf(length,0.05))),0.009,0.11)
