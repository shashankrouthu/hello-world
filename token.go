package main

import (
	"fmt"
	"os"
	"time"

	"github.com/dchest/authcookie"
)

func main() {
	// --- ✅ Read secret from environment variable ---
	secretStr := os.Getenv("TI_SERVICE_TOKEN")
	if secretStr == "" {
		fmt.Println("TI_SERVICE_TOKEN environment variable is not set")
		os.Exit(1)
	}
	secret := []byte(secretStr)

	// --- ✅ Your inputs ---
	accountID := "l7B_kbSEQD2wjrM7PShm5w"
	shouldIncreaseTTL := false

	// --- 🔐 Token expiry logic ---
	var expiryTime time.Duration
	if shouldIncreaseTTL {
		expiryTime = 1440 * time.Hour // 60 days
	} else {
		expiryTime = 48 * time.Hour
	}

	fmt.Println("Using expiry time:")
	fmt.Println(expiryTime)

	// --- 🔑 Generate token ---
	cookie := authcookie.NewSinceNow(accountID, expiryTime, secret)

	// --- 📤 Output ---
	fmt.Println("Generated Auth Cookie Token:")
	fmt.Println(cookie)
}
