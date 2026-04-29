package fflogs

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"time"
)

const (
	tokenURL   = "https://www.fflogs.com/oauth/token"
	apiURL     = "https://www.fflogs.com/api/v2/client"
)

type Client struct {
	httpClient  *http.Client
	accessToken string
}

func NewClient() (*Client, error) {
	c := &Client{httpClient: &http.Client{Timeout: 30 * time.Second}}
	if err := c.authenticate(); err != nil {
		return nil, err
	}
	return c, nil
}

func (c *Client) authenticate() error {
	data := url.Values{}
	data.Set("grant_type", "client_credentials")

	req, _ := http.NewRequest(http.MethodPost, tokenURL, bytes.NewBufferString(data.Encode()))
	req.SetBasicAuth(os.Getenv("FFLOGS_CLIENT_ID"), os.Getenv("FFLOGS_CLIENT_SECRET"))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("fflogs auth request failed: %w", err)
	}
	defer resp.Body.Close()

	var result struct {
		AccessToken string `json:"access_token"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return fmt.Errorf("fflogs auth decode failed: %w", err)
	}
	if result.AccessToken == "" {
		return fmt.Errorf("fflogs returned empty access token — check credentials")
	}

	c.accessToken = result.AccessToken
	return nil
}

type graphQLRequest struct {
	Query     string         `json:"query"`
	Variables map[string]any `json:"variables,omitempty"`
}

func (c *Client) Query(query string, variables map[string]any, result any) error {
	body, _ := json.Marshal(graphQLRequest{Query: query, Variables: variables})

	req, _ := http.NewRequest(http.MethodPost, apiURL, bytes.NewBuffer(body))
	req.Header.Set("Authorization", "Bearer "+c.accessToken)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("fflogs query failed: %w", err)
	}
	defer resp.Body.Close()

	var wrapper struct {
		Data   json.RawMessage `json:"data"`
		Errors []struct {
			Message string `json:"message"`
		} `json:"errors"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&wrapper); err != nil {
		return fmt.Errorf("fflogs response decode failed: %w", err)
	}
	if len(wrapper.Errors) > 0 {
		return fmt.Errorf("fflogs graphql error: %s", wrapper.Errors[0].Message)
	}

	return json.Unmarshal(wrapper.Data, result)
}
