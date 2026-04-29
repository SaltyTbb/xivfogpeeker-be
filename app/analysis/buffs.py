# Hardcoded raid buff ability IDs by job.
# Source: xivapi + community resources. Revisit and expand in future milestones.

RAID_BUFF_IDS: dict[str, list[int]] = {
    "AST":  [1878, 16552],        # Divination, Astrodyne
    "BRD":  [786, 1200],          # Battle Voice, Radiant Finale
    "DNC":  [1819, 2964],         # Technical Finish, Devilment
    "DRG":  [1181],               # Battle Litany
    "MNK":  [1185],               # Brotherhood
    "NIN":  [2248],               # Mug
    "RDM":  [7521],               # Embolden
    "RPR":  [2587],               # Arcane Circle
    "SCH":  [185],                # Chain Stratagem
    "SGE":  [3615],               # Physis II (team regen, counted as raid buff)
    "SMN":  [25801],              # Searing Light
    "VPR":  [3645],               # Serpent's Ire (TODO: verify ID)
    "PCT":  [34662],              # Starry Muse
}

# All raid buff IDs as a flat set for quick membership checks.
ALL_RAID_BUFF_IDS: set[int] = {
    ability_id
    for ids in RAID_BUFF_IDS.values()
    for ability_id in ids
}
