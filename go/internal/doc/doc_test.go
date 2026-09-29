package doc_test

import (
	"testing"

	"github.com/magiccityreader/Lightwrite/internal/doc"
)

func TestInsertAndEnter(t *testing.T) {
	d := doc.New()
	line, col := doc.InsertRunes(d, 0, 0, "hello", 0)
	if d.Lines[0] != "hello" || line != 0 || col != 5 {
		t.Fatalf("insert: %q %d %d", d.Lines[0], line, col)
	}
	line, col = doc.Enter(d, 0, 2)
	if d.Lines[0] != "he" || d.Lines[1] != "llo" || line != 1 || col != 0 {
		t.Fatalf("enter: %#v %d %d", d.Lines, line, col)
	}
}

func TestAttrToggle(t *testing.T) {
	d := doc.New()
	doc.InsertRunes(d, 0, 0, "hello", 0)
	doc.ApplyAttrToSelection(d, [2]int{0, 0}, [2]int{0, 5}, doc.Bold)
	for _, a := range d.Format[0] {
		if a&doc.Bold == 0 {
			t.Fatal("expected bold")
		}
	}
	doc.ApplyAttrToSelection(d, [2]int{0, 0}, [2]int{0, 5}, doc.Bold)
	for _, a := range d.Format[0] {
		if a&doc.Bold != 0 {
			t.Fatal("expected bold cleared")
		}
	}
}

func TestReplaceAll(t *testing.T) {
	d := doc.New()
	doc.InsertRunes(d, 0, 0, "alpha beta alpha", 0)
	n := doc.ReplaceAll(d, "alpha", "omega")
	if n != 2 || d.Lines[0] != "omega beta omega" {
		t.Fatalf("replace: n=%d %q", n, d.Lines[0])
	}
}

func TestWordCount(t *testing.T) {
	d := doc.New()
	doc.InsertRunes(d, 0, 0, "one two three", 0)
	if d.WordCount() != 3 {
		t.Fatal(d.WordCount())
	}
}
