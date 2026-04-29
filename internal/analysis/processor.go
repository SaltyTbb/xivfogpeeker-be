package analysis

import "fmt"

// AnalysisResult is the structured summary passed to the LLM and returned to the frontend.
type AnalysisResult struct {
	Fight            FightSummary       `json:"fight"`
	Deaths           []DeathEvent       `json:"deaths"`
	PerformanceFlags []PerformanceFlag  `json:"performance_flags"`
}

type FightSummary struct {
	Boss        string  `json:"boss"`
	DurationSec float64 `json:"duration_sec"`
	Outcome     string  `json:"outcome"` // "kill" | "wipe"
	FightPercent float64 `json:"fight_percent,omitempty"`
}

type DeathEvent struct {
	Player        string   `json:"player"`
	Job           string   `json:"job"`
	TimestampSec  float64  `json:"timestamp_sec"`
	OverkillDmg   int      `json:"overkill_dmg"`
	KillingAbility string  `json:"killing_ability"`
	ActiveDebuffs []string `json:"active_debuffs"`
	ActiveBuffs   []string `json:"active_buffs"`
}

type PerformanceFlag struct {
	Player string `json:"player"`
	Job    string `json:"job"`
	Issue  string `json:"issue"` // "low_uptime" | "interrupted_casts" | "missed_buff_windows"
	Detail string `json:"detail"`
}

// ToPromptContext serialises the result into a compact string for the LLM context.
func (a *AnalysisResult) ToPromptContext() string {
	out := fmt.Sprintf("Fight: %s | Duration: %.0fs | Outcome: %s\n\n", a.Fight.Boss, a.Fight.DurationSec, a.Fight.Outcome)

	if len(a.Deaths) == 0 {
		out += "Deaths: none\n\n"
	} else {
		out += "Deaths:\n"
		for _, d := range a.Deaths {
			out += fmt.Sprintf("  - %s (%s) at %.0fs — killed by %s, overkill %d, debuffs: %v, buffs: %v\n",
				d.Player, d.Job, d.TimestampSec, d.KillingAbility, d.OverkillDmg, d.ActiveDebuffs, d.ActiveBuffs)
		}
		out += "\n"
	}

	if len(a.PerformanceFlags) == 0 {
		out += "Performance flags: none\n"
	} else {
		out += "Performance flags:\n"
		for _, f := range a.PerformanceFlags {
			out += fmt.Sprintf("  - %s (%s): %s — %s\n", f.Player, f.Job, f.Issue, f.Detail)
		}
	}

	return out
}

// TODO M2: implement BuildDeaths(fights, events, actors) -> []DeathEvent
// TODO M3: implement BuildPerformanceFlags(events, actors, fightDuration) -> []PerformanceFlag
