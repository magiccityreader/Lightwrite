package smoke_test

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/magiccityreader/Lightwrite/internal/doc"
	"github.com/magiccityreader/Lightwrite/internal/docio"
	"github.com/magiccityreader/Lightwrite/internal/rtf"
	"github.com/magiccityreader/Lightwrite/internal/undo"
)

// Behavioral checklist ported from tests/smoke_pty.py (core path, no TTY).

func TestTypeUndo(t *testing.T) {
	d := doc.New()
	var s undo.Stack
	s.PushInsert(0, 0, "hello world")
	doc.InsertRunes(d, 0, 0, "hello world", 0)
	s.PushSpan(d, 0, 1)
	doc.Enter(d, 0, 11)
	s.PushInsert(1, 0, "second line")
	doc.InsertRunes(d, 1, 0, "second line", 0)
	if !strings.Contains(d.String(), "second line") {
		t.Fatal(d.String())
	}
	s.Apply(d) // undo typing second line via span before insert — stack order
	// simpler assert: undo insert coalesce
	d2 := doc.New()
	var s2 undo.Stack
	for i, ch := range "abc" {
		s2.PushInsert(0, i, string(ch))
		doc.InsertRunes(d2, 0, i, string(ch), 0)
	}
	s2.Apply(d2)
	if d2.Lines[0] != "" {
		t.Fatal(d2.Lines[0])
	}
}

func TestSaveLoadRTF(t *testing.T) {
	d := doc.New()
	doc.InsertRunes(d, 0, 0, "saved text", 0)
	dir := t.TempDir()
	path := filepath.Join(dir, "note.rtf")
	if err := docio.SaveDocument(d, path); err != nil {
		t.Fatal(err)
	}
	d2, err := docio.LoadDocument(path)
	if err != nil {
		t.Fatal(err)
	}
	if d2.Lines[0] != "saved text" {
		t.Fatal(d2.Lines[0])
	}
	b, _ := os.ReadFile(path)
	if !strings.Contains(string(b), `{\rtf`) {
		t.Fatal("not rtf")
	}
}

func TestFormattingInRTF(t *testing.T) {
	d := doc.New()
	doc.InsertRunes(d, 0, 0, "styled line", 0)
	doc.ApplyAttrToSelection(d, [2]int{0, 0}, [2]int{0, 11}, doc.Bold)
	doc.ApplyAlignment(d, 0, nil, nil, doc.AlignCenter)
	dir := t.TempDir()
	path := filepath.Join(dir, "fmt.rtf")
	if err := rtf.Save(d, path); err != nil {
		t.Fatal(err)
	}
	b, _ := os.ReadFile(path)
	body := string(b)
	if !strings.Contains(body, `\b`) || !strings.Contains(body, `\qc`) {
		t.Fatalf("missing styles: %s", body)
	}
}

func TestSearchReplace(t *testing.T) {
	d := doc.New()
	doc.InsertRunes(d, 0, 0, "alpha beta alpha", 0)
	hits := doc.FindAll(d, "alpha")
	if len(hits) != 2 {
		t.Fatal(hits)
	}
	var s undo.Stack
	s.PushSpan(d, 0, 1)
	n := doc.ReplaceAll(d, "alpha", "omega")
	if n != 2 || d.Lines[0] != "omega beta omega" {
		t.Fatal(n, d.Lines[0])
	}
	s.Apply(d)
	if d.Lines[0] != "alpha beta alpha" {
		t.Fatal(d.Lines[0])
	}
}

func TestPageBreakLongDoc(t *testing.T) {
	d := doc.New()
	doc.InsertPageBreak(d, 0, 0)
	for i := 0; i < 40; i++ {
		line := len(d.Lines) - 1
		col := len([]rune(d.Lines[line]))
		text := "line " + string(rune('0'+(i%10)))
		doc.InsertRunes(d, line, col, text, 0)
		doc.Enter(d, line, len([]rune(d.Lines[line])))
	}
	dir := t.TempDir()
	path := filepath.Join(dir, "long.rtf")
	if err := rtf.Save(d, path); err != nil {
		t.Fatal(err)
	}
	b, _ := os.ReadFile(path)
	if !strings.Contains(string(b), `\page`) {
		t.Fatal("missing page")
	}
}

func TestOpenArgvFixture(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "preload.rtf")
	_ = os.WriteFile(path, []byte(`{\rtf1\ansi\deff0 preloaded content\par}`), 0o644)
	d, err := docio.LoadDocument(path)
	if err != nil {
		t.Fatal(err)
	}
	if d.Lines[0] != "preloaded content" {
		t.Fatal(d.Lines[0])
	}
}

func TestCopyPasteCells(t *testing.T) {
	d := doc.New()
	doc.InsertRunes(d, 0, 0, "copy me", 0)
	cells := doc.SelectedCells(d, [2]int{0, 0}, [2]int{0, 7})
	d2 := doc.New()
	doc.InsertCells(d2, 0, 0, cells)
	if d2.Lines[0] != "copy me" {
		t.Fatal(d2.Lines[0])
	}
}
