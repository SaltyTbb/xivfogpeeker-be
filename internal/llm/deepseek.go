package llm

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"time"
)

const deepseekURL = "https://api.deepseek.com/chat/completions"

// Message is a single chat message (role + content).
type Message struct {
	Role    string `json:"role"`    // "system" | "user" | "assistant"
	Content string `json:"content"`
}

type Client struct {
	httpClient *http.Client
	apiKey     string
}

func NewClient() *Client {
	return &Client{
		httpClient: &http.Client{Timeout: 60 * time.Second},
		apiKey:     os.Getenv("DEEPSEEK_API_KEY"),
	}
}

// Chat sends a conversation to DeepSeek and returns the assistant reply.
func (c *Client) Chat(messages []Message) (string, error) {
	payload := map[string]any{
		"model":    "deepseek-chat",
		"messages": messages,
	}
	body, _ := json.Marshal(payload)

	req, _ := http.NewRequest(http.MethodPost, deepseekURL, bytes.NewBuffer(body))
	req.Header.Set("Authorization", "Bearer "+c.apiKey)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("deepseek request failed: %w", err)
	}
	defer resp.Body.Close()

	var result struct {
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
		} `json:"choices"`
		Error *struct {
			Message string `json:"message"`
		} `json:"error"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return "", fmt.Errorf("deepseek response decode failed: %w", err)
	}
	if result.Error != nil {
		return "", fmt.Errorf("deepseek error: %s", result.Error.Message)
	}
	if len(result.Choices) == 0 {
		return "", fmt.Errorf("deepseek returned no choices")
	}

	return result.Choices[0].Message.Content, nil
}

const systemPrompt = `You are a FFXIV raid log analyst.
Your job is to describe what happened in the raid factually and concisely.
Do NOT give improvement suggestions or coaching advice.
When asked about a death, explain the circumstances (debuffs, incoming damage, overkill amount).
When asked about performance, state what the numbers show.
Keep answers short and direct.`

func SystemPrompt() Message {
	return Message{Role: "system", Content: systemPrompt}
}
