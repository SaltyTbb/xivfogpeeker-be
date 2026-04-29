package handler

import (
	"encoding/json"
	"net/http"

	"github.com/yuanbo/xivfogpeeker-be/internal/llm"
)

type chatRequest struct {
	Context  string        `json:"context"`   // serialised fight context from /analyze
	History  []llm.Message `json:"history"`   // prior conversation turns
	Question string        `json:"question"`
}

type chatResponse struct {
	Answer  string        `json:"answer"`
	History []llm.Message `json:"history"` // updated history to pass back next turn
}

// Chat handles POST /chat
// Accepts the prior context + conversation history and answers a follow-up question.
func Chat(w http.ResponseWriter, r *http.Request) {
	var req chatRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		jsonError(w, "invalid request body", http.StatusBadRequest)
		return
	}
	if req.Question == "" {
		jsonError(w, "question is required", http.StatusBadRequest)
		return
	}

	messages := []llm.Message{llm.SystemPrompt()}
	if req.Context != "" {
		messages = append(messages, llm.Message{
			Role:    "user",
			Content: "Fight context:\n\n" + req.Context,
		}, llm.Message{
			Role:    "assistant",
			Content: "Understood. Ask me anything about this fight.",
		})
	}
	messages = append(messages, req.History...)
	messages = append(messages, llm.Message{Role: "user", Content: req.Question})

	llmClient := llm.NewClient()
	answer, err := llmClient.Chat(messages)
	if err != nil {
		jsonError(w, "llm call failed: "+err.Error(), http.StatusInternalServerError)
		return
	}

	updatedHistory := append(req.History, llm.Message{Role: "user", Content: req.Question})
	updatedHistory = append(updatedHistory, llm.Message{Role: "assistant", Content: answer})

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(chatResponse{
		Answer:  answer,
		History: updatedHistory,
	})
}

func jsonError(w http.ResponseWriter, msg string, code int) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(map[string]string{"error": msg})
}
