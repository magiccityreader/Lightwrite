package rtf_test

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/magiccityreader/Lightwrite/internal/doc"
	"github.com/magiccityreader/Lightwrite/internal/rtf"
)

func TestRoundTrip(t *testing.T) {
	d := doc.New()
	doc.InsertRunes(d, 0, 0, "Hola", doc.Bold)
	doc.Enter(d, 0, 4)
	doc.InsertRunes(d, 1, 0, "mundo", doc.Italic)
	dir := t.TempDir()
	path := filepath.Join(dir, "t.rtf")
	if err := rtf.Save(d, path); err != nil {
		t.Fatal(err)
	}
	b, _ := os.ReadFile(path)
	if !strings.HasPrefix(strings.TrimSpace(string(b)), `{\rtf`) {
		t.Fatal("not rtf")
	}
	d2 := rtf.Parse(string(b))
	plain := strings.ReplaceAll(d2.String(), "\r", "")
	if plain != "Hola\nmundo" {
		t.Fatalf("got %q", plain)
	}
}

func TestParseMinimal(t *testing.T) {
	d := rtf.Parse(`{\rtf1\ansi\deff0 preloaded content\par}`)
	if d.Lines[0] != "preloaded content" {
		t.Fatalf("%q", d.Lines[0])
	}
}
