package fflogs

// Fight represents a single pull within an FFLogs report.
type Fight struct {
	ID           int    `json:"id"`
	Name         string `json:"name"`
	StartTime    int64  `json:"startTime"`
	EndTime      int64  `json:"endTime"`
	Kill         bool   `json:"kill"`
	FightPercent float64 `json:"fightPercentage"`
}

// Actor represents a player or NPC in the report.
type Actor struct {
	ID   int    `json:"id"`
	Name string `json:"name"`
	Type string `json:"type"` // "Player" | "NPC"
	SubType string `json:"subType"` // job abbreviation e.g. "DRK"
}

// GetFights fetches all fights in a report.
func (c *Client) GetFights(reportCode string) ([]Fight, error) {
	const q = `
	query($code: String!) {
		reportData {
			report(code: $code) {
				fights {
					id name startTime endTime kill fightPercentage
				}
			}
		}
	}`

	var data struct {
		ReportData struct {
			Report struct {
				Fights []Fight `json:"fights"`
			} `json:"report"`
		} `json:"reportData"`
	}
	if err := c.Query(q, map[string]any{"code": reportCode}, &data); err != nil {
		return nil, err
	}
	return data.ReportData.Report.Fights, nil
}

// GetActors fetches the player roster for a report.
func (c *Client) GetActors(reportCode string) ([]Actor, error) {
	const q = `
	query($code: String!) {
		reportData {
			report(code: $code) {
				masterData {
					actors(type: "Player") {
						id name type subType
					}
				}
			}
		}
	}`

	var data struct {
		ReportData struct {
			Report struct {
				MasterData struct {
					Actors []Actor `json:"actors"`
				} `json:"masterData"`
			} `json:"report"`
		} `json:"reportData"`
	}
	if err := c.Query(q, map[string]any{"code": reportCode}, &data); err != nil {
		return nil, err
	}
	return data.ReportData.Report.MasterData.Actors, nil
}

// RawEvent is a generic FFLogs event entry.
type RawEvent struct {
	Timestamp    int64          `json:"timestamp"`
	Type         string         `json:"type"`
	SourceID     int            `json:"sourceID"`
	TargetID     int            `json:"targetID"`
	AbilityGameID int           `json:"abilityGameID"`
	AbilityName  string         `json:"abilityName"`
	Amount       int            `json:"amount"`
	Overkill     int            `json:"overkill"`
	Buffs        string         `json:"buffs"` // bitmask string from FFLogs
}

// GetEvents fetches raw events for a specific fight.
func (c *Client) GetEvents(reportCode string, fightID int, eventTypes []string) ([]RawEvent, error) {
	const q = `
	query($code: String!, $fightIDs: [Int], $dataType: EventDataType!) {
		reportData {
			report(code: $code) {
				events(fightIDs: $fightIDs, dataType: $dataType, limit: 10000) {
					data
					nextPageTimestamp
				}
			}
		}
	}`

	// TODO: support pagination via nextPageTimestamp
	// TODO: map eventTypes to FFLogs EventDataType enum (Deaths, DamageTaken, Casts, Buffs)
	_ = eventTypes

	var data struct {
		ReportData struct {
			Report struct {
				Events struct {
					Data              []RawEvent `json:"data"`
					NextPageTimestamp *int64     `json:"nextPageTimestamp"`
				} `json:"events"`
			} `json:"report"`
		} `json:"reportData"`
	}
	if err := c.Query(q, map[string]any{
		"code":     reportCode,
		"fightIDs": []int{fightID},
		"dataType": "Deaths",
	}, &data); err != nil {
		return nil, err
	}
	return data.ReportData.Report.Events.Data, nil
}
