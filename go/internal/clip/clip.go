package clip

import (
	"os/exec"
	"strings"

	"github.com/magiccityreader/Lightwrite/internal/doc"
)

var InternalRich []doc.Cell

func Set(text string) {
	if _, err := exec.LookPath("xclip"); err == nil {
		cmd := exec.Command("xclip", "-selection", "clipboard")
		cmd.Stdin = strings.NewReader(text)
		_ = cmd.Run()
		return
	}
	if _, err := exec.LookPath("xsel"); err == nil {
		cmd := exec.Command("xsel", "--clipboard", "--input")
		cmd.Stdin = strings.NewReader(text)
		_ = cmd.Run()
		return
	}
	// Windows
	if _, err := exec.LookPath("clip.exe"); err == nil {
		cmd := exec.Command("clip.exe")
		cmd.Stdin = strings.NewReader(text)
		_ = cmd.Run()
	}
}

func Get() string {
	if _, err := exec.LookPath("xclip"); err == nil {
		out, err := exec.Command("xclip", "-selection", "clipboard", "-o").Output()
		if err == nil {
			return string(out)
		}
	}
	if _, err := exec.LookPath("xsel"); err == nil {
		out, err := exec.Command("xsel", "--clipboard", "--output").Output()
		if err == nil {
			return string(out)
		}
	}
	return doc.CellsToText(InternalRich)
}
