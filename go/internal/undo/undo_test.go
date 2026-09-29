package undo_test

import (
	"testing"

	"github.com/magiccityreader/Lightwrite/internal/doc"
	"github.com/magiccityreader/Lightwrite/internal/undo"
)

func TestInsertCoalesceAndUndo(t *testing.T) {
	d := doc.New()
	var s undo.Stack
	for i, ch := range "abc" {
		s.PushInsert(0, i, string(ch))
		doc.InsertRunes(d, 0, i, string(ch), 0)
	}
	if s.Len() != 1 {
		t.Fatalf("expected coalesced insert, got %d", s.Len())
	}
	if !s.Apply(d) || d.Lines[0] != "" {
		t.Fatalf("undo insert: %q", d.Lines[0])
	}
}

func TestSpanUndo(t *testing.T) {
	d := doc.New()
	doc.InsertRunes(d, 0, 0, "hello", 0)
	var s undo.Stack
	s.PushSpan(d, 0, 1)
	doc.InsertRunes(d, 0, 5, "!", 0)
	if d.Lines[0] != "hello!" {
		t.Fatal(d.Lines[0])
	}
	s.Apply(d)
	if d.Lines[0] != "hello" {
		t.Fatalf("span undo: %q", d.Lines[0])
	}
}

func TestSpaceBreaksCoalesce(t *testing.T) {
	var s undo.Stack
	s.PushInsert(0, 0, "a")
	s.PushInsert(0, 1, " ")
	s.PushInsert(0, 2, "b")
	if s.Len() != 3 {
		t.Fatal(s.Len())
	}
}
