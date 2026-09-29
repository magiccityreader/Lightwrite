package spell

import (
	"os/exec"
	"strings"
)

func Tool() string {
	if _, err := exec.LookPath("hunspell"); err == nil {
		return "hunspell"
	}
	if _, err := exec.LookPath("aspell"); err == nil {
		return "aspell"
	}
	return ""
}

// Check returns byte offsets [start,end) of misspelled words, or nil if unavailable.
func Check(text, lang string) ([][2]int, error) {
	tool := Tool()
	if tool == "" {
		return nil, nil
	}
	var cmd *exec.Cmd
	if tool == "hunspell" {
		cmd = exec.Command("hunspell", "-l", "-d", langOrDefault(lang))
	} else {
		cmd = exec.Command("aspell", "-a", "--lang="+langOrDefault(lang))
	}
	cmd.Stdin = strings.NewReader(text)
	out, err := cmd.Output()
	if err != nil {
		// hunspell -l returns misspellings one per line
	}
	if tool == "hunspell" {
		words := strings.Fields(string(out))
		lower := strings.ToLower(text)
		var pos [][2]int
		for _, w := range words {
			w = strings.TrimSpace(w)
			if w == "" {
				continue
			}
			idx := strings.Index(lower, strings.ToLower(w))
			for idx >= 0 {
				pos = append(pos, [2]int{idx, idx + len(w)})
				next := strings.Index(lower[idx+len(w):], strings.ToLower(w))
				if next < 0 {
					break
				}
				idx = idx + len(w) + next
			}
		}
		return pos, nil
	}
	_ = out
	return [][2]int{}, nil
}

func Suggestions(word, lang string) []string {
	tool := Tool()
	if tool == "" {
		return nil
	}
	var cmd *exec.Cmd
	if tool == "hunspell" {
		cmd = exec.Command("hunspell", "-d", langOrDefault(lang))
		cmd.Stdin = strings.NewReader(word + "\n")
	} else {
		return nil
	}
	out, err := cmd.Output()
	if err != nil {
		return nil
	}
	for _, line := range strings.Split(string(out), "\n") {
		if strings.HasPrefix(line, "&") {
			parts := strings.SplitN(line, ":", 2)
			if len(parts) == 2 {
				var sug []string
				for _, s := range strings.Split(parts[1], ",") {
					s = strings.TrimSpace(s)
					if s != "" {
						sug = append(sug, s)
					}
				}
				return sug
			}
		}
	}
	return nil
}

func langOrDefault(lang string) string {
	switch lang {
	case "en":
		return "en_US"
	case "es":
		return "es_ES"
	default:
		if lang == "" {
			return "en_US"
		}
		return lang
	}
}
