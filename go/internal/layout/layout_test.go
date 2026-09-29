package layout_test

import (
	"testing"

	"github.com/magiccityreader/Lightwrite/internal/doc"
	"github.com/magiccityreader/Lightwrite/internal/layout"
)

func TestVisualLinesWrap(t *testing.T) {
	lines := layout.ComputeVisualLines([]string{"word word word word word"}, 10)
	if len(lines) < 2 {
		t.Fatalf("expected wrap, got %d", len(lines))
	}
}

func TestCacheHit(t *testing.T) {
	d := doc.New()
	doc.InsertRunes(d, 0, 0, "hello world", 0)
	var c layout.Cache
	a := c.VisualLines(d, 20)
	b := c.VisualLines(d, 20)
	if len(a) != len(b) {
		t.Fatal("cache mismatch")
	}
	d.Bump()
	doc.InsertRunes(d, 0, 0, "x", 0)
	c2 := c.VisualLines(d, 20)
	if len(c2) < 1 {
		t.Fatal("recompute failed")
	}
}

func TestCursorPosition(t *testing.T) {
	d := doc.New()
	doc.InsertRunes(d, 0, 0, "hello", 0)
	row, x := layout.CursorVisualPosition(d, 0, 3, 80, nil)
	if row != 0 || x != 3 {
		t.Fatalf("%d %d", row, x)
	}
}
