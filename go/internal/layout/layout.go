package layout

import (
	"github.com/magiccityreader/Lightwrite/internal/doc"
	"github.com/rivo/uniseg"
)

type VisualLine struct {
	LineIndex int
	Start     int
	Text      string
}

type Cache struct {
	key   [4]int // version, width, id-proxy, len
	lines []VisualLine
	valid bool
}

func (c *Cache) Invalidate() {
	c.valid = false
	c.lines = nil
}

func (c *Cache) VisualLines(d *doc.Document, width int) []VisualLine {
	key := [4]int{d.Version, width, 0, len(d.Lines)}
	if c.valid && c.key == key {
		return c.lines
	}
	c.lines = ComputeVisualLines(d.Lines, width)
	c.key = key
	c.valid = true
	return c.lines
}

func DisplayWidth(s string) int {
	return uniseg.StringWidth(s)
}

func ComputeVisualLines(lines []string, width int) []VisualLine {
	var result []VisualLine
	for lineIndex, line := range lines {
		if line == "" {
			result = append(result, VisualLine{LineIndex: lineIndex, Start: 0, Text: ""})
			continue
		}
		runes := []rune(line)
		start := 0
		for start < len(runes) {
			remaining := string(runes[start:])
			remRunes := runes[start:]
			if len(remRunes) <= width {
				result = append(result, VisualLine{LineIndex: lineIndex, Start: start, Text: remaining})
				break
			}
			cut := -1
			limit := width
			if limit > len(remRunes) {
				limit = len(remRunes)
			}
			for i := 0; i < limit && i < len(remRunes); i++ {
				if remRunes[i] == ' ' {
					cut = i
				}
			}
			// rfind space in [0, width+1)
			cut = -1
			maxSearch := width + 1
			if maxSearch > len(remRunes) {
				maxSearch = len(remRunes)
			}
			for i := 0; i < maxSearch; i++ {
				if remRunes[i] == ' ' {
					cut = i
				}
			}
			if cut <= 0 {
				cut = width
			}
			piece := string(remRunes[:cut])
			result = append(result, VisualLine{LineIndex: lineIndex, Start: start, Text: piece})
			start += cut
			for start < len(runes) && runes[start] == ' ' {
				start++
			}
		}
	}
	if len(result) == 0 {
		result = append(result, VisualLine{LineIndex: 0, Start: 0, Text: ""})
	}
	return result
}

func CursorVisualPosition(d *doc.Document, cursorLine, cursorCol, width int, cache *Cache) (row, x int) {
	var lines []VisualLine
	if cache != nil {
		lines = cache.VisualLines(d, width)
	} else {
		lines = ComputeVisualLines(d.Lines, width)
	}
	for row, vl := range lines {
		if vl.LineIndex != cursorLine {
			continue
		}
		end := vl.Start + len([]rune(vl.Text))
		if vl.Start <= cursorCol && cursorCol <= end {
			return row, cursorCol - vl.Start
		}
	}
	if len(lines) == 0 {
		return 0, 0
	}
	last := lines[len(lines)-1]
	if last.LineIndex == cursorLine {
		return len(lines) - 1, max(0, cursorCol-last.Start)
	}
	return 0, 0
}

func AdjustScroll(d *doc.Document, cursorLine, cursorCol, width, visibleRows, scrollRow int, cache *Cache) int {
	cursorRow, _ := CursorVisualPosition(d, cursorLine, cursorCol, width, cache)
	if cursorRow < scrollRow {
		scrollRow = cursorRow
	} else if cursorRow >= scrollRow+visibleRows {
		scrollRow = cursorRow - visibleRows + 1
	}
	if scrollRow < 0 {
		return 0
	}
	return scrollRow
}

func MoveUp(d *doc.Document, cursorLine, cursorCol, textWidth int, cache *Cache) (int, int) {
	row, x := CursorVisualPosition(d, cursorLine, cursorCol, textWidth, cache)
	if row <= 0 {
		return cursorLine, cursorCol
	}
	lines := ComputeVisualLines(d.Lines, textWidth)
	if cache != nil {
		lines = cache.VisualLines(d, textWidth)
	}
	target := lines[row-1]
	col := target.Start + min(x, len([]rune(target.Text)))
	return target.LineIndex, col
}

func MoveDown(d *doc.Document, cursorLine, cursorCol, textWidth int, cache *Cache) (int, int) {
	row, x := CursorVisualPosition(d, cursorLine, cursorCol, textWidth, cache)
	lines := ComputeVisualLines(d.Lines, textWidth)
	if cache != nil {
		lines = cache.VisualLines(d, textWidth)
	}
	if row >= len(lines)-1 {
		return cursorLine, cursorCol
	}
	target := lines[row+1]
	col := target.Start + min(x, len([]rune(target.Text)))
	return target.LineIndex, col
}

func ComputeLineLayout(text string, textWidth int, align doc.Align, isLastSubline bool) (display string, offset int, mapping []int) {
	n := len([]rune(text))
	switch align {
	case doc.AlignCenter:
		return text, max(0, (textWidth-n)/2), nil
	case doc.AlignRight:
		return text, max(0, textWidth-n), nil
	case doc.AlignJustify:
		if !isLastSubline {
			words := splitWords(text)
			if len(words) >= 2 {
				totalChars := 0
				for _, w := range words {
					totalChars += len([]rune(w))
				}
				gaps := len(words) - 1
				extra := textWidth - totalChars - gaps
				if extra > 0 {
					extraPer := extra / gaps
					rem := extra % gaps
					var result []rune
					var mapOut []int
					pos := 0
					runes := []rune(text)
					for wi, w := range words {
						wp := indexFrom(runes, []rune(w), pos)
						for k, c := range []rune(w) {
							result = append(result, c)
							mapOut = append(mapOut, wp+k)
						}
						pos = wp + len([]rune(w))
						if wi < len(words)-1 {
							spaceCol := wp + len([]rune(w))
							num := 1 + extraPer
							if wi < rem {
								num++
							}
							for p := 0; p < num; p++ {
								result = append(result, ' ')
								mapOut = append(mapOut, spaceCol)
							}
						}
					}
					return string(result), 0, mapOut
				}
			}
		}
	}
	return text, 0, nil
}

func splitWords(text string) []string {
	var words []string
	for _, w := range splitKeep(text, ' ') {
		if w != "" {
			words = append(words, w)
		}
	}
	return words
}

func splitKeep(s string, sep rune) []string {
	var out []string
	var cur []rune
	for _, r := range s {
		if r == sep {
			out = append(out, string(cur))
			cur = nil
		} else {
			cur = append(cur, r)
		}
	}
	out = append(out, string(cur))
	return out
}

func indexFrom(hay, needle []rune, start int) int {
	for i := start; i+len(needle) <= len(hay); i++ {
		match := true
		for j := range needle {
			if hay[i+j] != needle[j] {
				match = false
				break
			}
		}
		if match {
			return i
		}
	}
	return start
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}
