package handler

import (
	"encoding/json"
	"net/http"

	"github.com/yuanbo/xivfogpeeker-be/internal/analysis"
	"github.com/yuanbo/xivfogpeeker-be/internal/llm"
)

type analyzeRequest struct {
	ReportCode string `json:"report_code"`
	FightID    int    `json:"fight_id"`
}

type analyzeResponse struct {
	Analysis  *analysis.AnalysisResult `json:"analysis"`
	Summary   string                   `json:"summary"`    // LLM one-shot summary
	Context   string                   `json:"context"`    // serialised context to pass back for Q&A
}

// Analyze handles POST /analyze
// Fetches fight data, builds structured analysis, generates LLM summary.
func Analyze(w http.ResponseWriter, r *http.Request) {
	var req analyzeRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		jsonError(w, "invalid request body", http.StatusBadRequest)
		return
	}
	if req.ReportCode == "" || req.FightID == 0 {
		jsonError(w, "report_code and fight_id are required", http.StatusBadRequest)
		return
	}

	// TODO M2/M3: fetch real events and build analysis
	// Placeholder stub so the route compiles and wires through end-to-end
	result := &analysis.AnalysisResult{
		Fight: analysis.FightSummary{
			Boss:        "TODO",
			DurationSec: 0,
			Outcome:     "TODO",
		},
	}

	llmClient := llm.NewClient()
	messages := []llm.Message{
		llm.SystemPrompt(),
		{Role: "user", Content: "Here is the fight data:\n\n" + result.ToPromptContext() + "\n\nSummarise what happened."},
	}

	summary, err := llmClient.Chat(messages)
	if err != nil {
		jsonError(w, "llm call failed: "+err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(analyzeResponse{
		Analysis: result,
		Summary:  summary,
		Context:  result.ToPromptContext(),
	})
}
