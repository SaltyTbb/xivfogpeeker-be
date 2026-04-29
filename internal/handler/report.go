package handler

import (
	"encoding/json"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/yuanbo/xivfogpeeker-be/internal/fflogs"
)

// GetFights handles GET /report/{code}
// Returns the list of fights so the frontend can show a fight picker.
func GetFights(w http.ResponseWriter, r *http.Request) {
	code := chi.URLParam(r, "code")

	client, err := fflogs.NewClient()
	if err != nil {
		jsonError(w, "fflogs auth failed: "+err.Error(), http.StatusInternalServerError)
		return
	}

	fights, err := client.GetFights(code)
	if err != nil {
		jsonError(w, "failed to fetch fights: "+err.Error(), http.StatusBadGateway)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(fights)
}
