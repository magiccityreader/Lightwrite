package ui

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/charmbracelet/bubbles/textinput"
	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/magiccityreader/Lightwrite/internal/clip"
	"github.com/magiccityreader/Lightwrite/internal/doc"
	"github.com/magiccityreader/Lightwrite/internal/docio"
	"github.com/magiccityreader/Lightwrite/internal/i18n"
	"github.com/magiccityreader/Lightwrite/internal/layout"
	"github.com/magiccityreader/Lightwrite/internal/undo"
)

type mode int

const (
	modeEdit mode = iota
	modeFind
	modeReplaceFind
	modeReplaceWith
	modeSaveAs
	modeConfirmQuit
	modeConfirmNew
	modeConfirmOpen
	modeConfirmOverwrite
	modeBrowse
	modeHelp
	modeAbout
	modeChapters
)

type Model struct {
	doc           *doc.Document
	path          string
	dirty         bool
	undo          undo.Stack
	cache         layout.Cache
	cursorLine    int
	cursorCol     int
	scrollRow     int
	selStart      *[2]int
	selEnd        *[2]int
	typingAttrs   doc.Attr
	mode          mode
	status        string
	statusAt      time.Time
	width, height int
	input         textinput.Model
	viewport      viewport.Model
	searchTerm    string
	replaceTerm   string
	searchMatches [][2]int
	searchIndex   int
	browseDir     string
	browseEntries []os.DirEntry
	browseIndex   int
	pendingPath   string
	helpScroll    int
	menuOpen      int // -1 closed
	menuSelected  int
	quitting      bool
}

func New(path string) (Model, error) {
	_ = docio.EnsureDirs()
	m := Model{
		doc:      doc.New(),
		menuOpen: -1,
		input:    textinput.New(),
	}
	m.input.CharLimit = 256
	m.viewport = viewport.New(80, 20)
	if path != "" {
		d, err := docio.LoadDocument(path)
		if err != nil {
			return m, err
		}
		m.doc = d
		m.path = path
	}
	return m, nil
}

func (m Model) Init() tea.Cmd { return textinput.Blink }

type tickMsg time.Time

func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width, m.height = msg.Width, msg.Height
		m.viewport.Width = msg.Width
		m.viewport.Height = max(1, msg.Height-6)
		return m, nil
	case tea.KeyMsg:
		return m.handleKey(msg)
	case tickMsg:
		if m.status != "" && time.Since(m.statusAt) > 1600*time.Millisecond {
			m.status = ""
		}
		return m, nil
	}
	if m.mode == modeFind || m.mode == modeReplaceFind || m.mode == modeReplaceWith ||
		m.mode == modeSaveAs || m.isConfirm() {
		var cmd tea.Cmd
		m.input, cmd = m.input.Update(msg)
		return m, cmd
	}
	return m, nil
}

func (m Model) isConfirm() bool {
	return m.mode == modeConfirmQuit || m.mode == modeConfirmNew ||
		m.mode == modeConfirmOpen || m.mode == modeConfirmOverwrite
}

func (m Model) handleKey(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	key := msg.String()

	if m.mode == modeHelp || m.mode == modeAbout {
		switch key {
		case "esc", "q", "enter":
			m.mode = modeEdit
		case "up", "k":
			m.helpScroll = max(0, m.helpScroll-1)
		case "down", "j":
			m.helpScroll++
		}
		return m, nil
	}

	if m.mode == modeBrowse {
		return m.handleBrowse(key)
	}

	if m.isConfirm() {
		return m.handleConfirm(key)
	}

	if m.mode == modeFind || m.mode == modeReplaceFind || m.mode == modeReplaceWith || m.mode == modeSaveAs {
		switch key {
		case "esc":
			m.mode = modeEdit
			m.input.Blur()
			return m, nil
		case "enter":
			return m.submitPrompt()
		}
		var cmd tea.Cmd
		m.input, cmd = m.input.Update(msg)
		return m, cmd
	}

	// Menu navigation
	if m.menuOpen >= 0 {
		return m.handleMenu(key)
	}

	switch key {
	case "ctrl+c":
		m.copySel()
	case "ctrl+x":
		m.cutSel()
	case "ctrl+v":
		m.paste()
	case "ctrl+z":
		if m.undo.Apply(m.doc) {
			m.dirty = true
			m.setStatus(i18n.Tr("Deshecho"))
		} else {
			m.setStatus(i18n.Tr("Nada que deshacer"))
		}
	case "ctrl+s":
		return m.save()
	case "ctrl+w":
		m.beginSaveAs(false)
	case "ctrl+n":
		if m.dirty {
			m.beginConfirm(modeConfirmNew)
		} else {
			m.newDoc()
		}
	case "ctrl+o":
		if m.dirty {
			m.beginConfirm(modeConfirmOpen)
		} else {
			m.openBrowser()
		}
	case "ctrl+q":
		if m.dirty {
			m.beginConfirm(modeConfirmQuit)
		} else {
			m.quitting = true
			return m, tea.Quit
		}
	case "ctrl+f":
		m.mode = modeFind
		m.input.SetValue("")
		m.input.Placeholder = "Find…"
		m.input.Focus()
	case "ctrl+r":
		m.mode = modeReplaceFind
		m.input.SetValue("")
		m.input.Placeholder = "Find…"
		m.input.Focus()
	case "ctrl+b":
		m.toggleAttr(doc.Bold)
	case "ctrl+i":
		m.toggleAttr(doc.Italic)
	case "ctrl+u":
		m.toggleAttr(doc.Underline)
	case "ctrl+a":
		last := len(m.doc.Lines) - 1
		m.selStart = &[2]int{0, 0}
		m.selEnd = &[2]int{last, utf8.RuneCountInString(m.doc.Lines[last])}
		m.cursorLine, m.cursorCol = last, utf8.RuneCountInString(m.doc.Lines[last])
	case "ctrl+g":
		m.mode = modeHelp
		m.helpScroll = 0
	case "ctrl+h":
		m.mode = modeAbout
		m.helpScroll = 0
	case "ctrl+t":
		m.mode = modeChapters
	case "ctrl+k":
		m.undo.PushSpan(m.doc, m.cursorLine, m.cursorLine+1)
		m.cursorLine, m.cursorCol = doc.InsertPageBreak(m.doc, m.cursorLine, m.cursorCol)
		m.dirty = true
		m.setStatus(i18n.Tr("Salto de página"))
	case "f9":
		m.menuOpen = 0
		m.menuSelected = 0
	case "esc":
		m.selStart, m.selEnd = nil, nil
		m.menuOpen = -1
	case "left":
		m.cursorLine, m.cursorCol = doc.MoveLeft(m.doc, m.cursorLine, m.cursorCol)
		m.clearSelUnlessShift(msg)
	case "right":
		m.cursorLine, m.cursorCol = doc.MoveRight(m.doc, m.cursorLine, m.cursorCol)
		m.clearSelUnlessShift(msg)
	case "up":
		m.cursorLine, m.cursorCol = layout.MoveUp(m.doc, m.cursorLine, m.cursorCol, textWidth(m.width), &m.cache)
		m.clearSelUnlessShift(msg)
	case "down":
		m.cursorLine, m.cursorCol = layout.MoveDown(m.doc, m.cursorLine, m.cursorCol, textWidth(m.width), &m.cache)
		m.clearSelUnlessShift(msg)
	case "backspace":
		m.deleteBackward()
	case "delete":
		m.deleteForward()
	case "enter":
		m.undo.PushSpan(m.doc, m.cursorLine, m.cursorLine+1)
		m.cursorLine, m.cursorCol = doc.Enter(m.doc, m.cursorLine, m.cursorCol)
		m.dirty = true
		m.selStart, m.selEnd = nil, nil
	case "home":
		m.cursorCol = 0
	case "end":
		m.cursorCol = utf8.RuneCountInString(m.doc.Lines[m.cursorLine])
	case "pgup":
		for i := 0; i < m.viewport.Height; i++ {
			m.cursorLine, m.cursorCol = layout.MoveUp(m.doc, m.cursorLine, m.cursorCol, textWidth(m.width), &m.cache)
		}
	case "pgdown":
		for i := 0; i < m.viewport.Height; i++ {
			m.cursorLine, m.cursorCol = layout.MoveDown(m.doc, m.cursorLine, m.cursorCol, textWidth(m.width), &m.cache)
		}
	default:
		if msg.Type == tea.KeyRunes && !msg.Alt {
			s := string(msg.Runes)
			if m.selStart != nil && m.selEnd != nil {
				m.undo.PushSpan(m.doc, 0, len(m.doc.Lines))
				m.cursorLine, m.cursorCol = doc.DeleteSelection(m.doc, *m.selStart, *m.selEnd)
				m.selStart, m.selEnd = nil, nil
			}
			m.undo.PushInsert(m.cursorLine, m.cursorCol, s)
			m.cursorLine, m.cursorCol = doc.InsertRunes(m.doc, m.cursorLine, m.cursorCol, s, m.typingAttrs)
			m.dirty = true
		}
	}
	m.scrollRow = layout.AdjustScroll(m.doc, m.cursorLine, m.cursorCol, textWidth(m.width), max(1, m.height-6), m.scrollRow, &m.cache)
	return m, nil
}

func (m *Model) clearSelUnlessShift(msg tea.KeyMsg) {
	if !msg.Alt { // bubbletea uses Shift in key names as "shift+left"
		if !strings.HasPrefix(msg.String(), "shift+") {
			m.selStart, m.selEnd = nil, nil
		}
	}
}

func (m *Model) setStatus(s string) {
	m.status = s
	m.statusAt = time.Now()
}

func (m *Model) toggleAttr(a doc.Attr) {
	if m.selStart != nil && m.selEnd != nil {
		m.undo.PushSpan(m.doc, 0, len(m.doc.Lines))
		doc.ApplyAttrToSelection(m.doc, *m.selStart, *m.selEnd, a)
		m.dirty = true
	} else {
		m.typingAttrs ^= a
	}
}

func (m *Model) deleteBackward() {
	if m.selStart != nil && m.selEnd != nil {
		m.undo.PushSpan(m.doc, 0, len(m.doc.Lines))
		m.cursorLine, m.cursorCol = doc.DeleteSelection(m.doc, *m.selStart, *m.selEnd)
		m.selStart, m.selEnd = nil, nil
	} else {
		m.undo.PushSpan(m.doc, max(0, m.cursorLine-1), m.cursorLine+1)
		m.cursorLine, m.cursorCol = doc.DeleteBefore(m.doc, m.cursorLine, m.cursorCol)
	}
	m.dirty = true
}

func (m *Model) deleteForward() {
	if m.selStart != nil && m.selEnd != nil {
		m.undo.PushSpan(m.doc, 0, len(m.doc.Lines))
		m.cursorLine, m.cursorCol = doc.DeleteSelection(m.doc, *m.selStart, *m.selEnd)
		m.selStart, m.selEnd = nil, nil
	} else {
		m.undo.PushSpan(m.doc, m.cursorLine, m.cursorLine+2)
		m.cursorLine, m.cursorCol = doc.DeleteAt(m.doc, m.cursorLine, m.cursorCol)
	}
	m.dirty = true
}

func (m *Model) copySel() {
	if m.selStart == nil || m.selEnd == nil {
		return
	}
	cells := doc.SelectedCells(m.doc, *m.selStart, *m.selEnd)
	clip.InternalRich = cells
	clip.Set(doc.CellsToText(cells))
	m.setStatus(i18n.Tr("Copiado"))
}

func (m *Model) cutSel() {
	if m.selStart == nil || m.selEnd == nil {
		return
	}
	m.copySel()
	m.undo.PushSpan(m.doc, 0, len(m.doc.Lines))
	m.cursorLine, m.cursorCol = doc.DeleteSelection(m.doc, *m.selStart, *m.selEnd)
	m.selStart, m.selEnd = nil, nil
	m.dirty = true
	m.setStatus(i18n.Tr("Cortado"))
}

func (m *Model) paste() {
	plain := clip.Get()
	richPlain := doc.CellsToText(clip.InternalRich)
	var cells []doc.Cell
	if len(clip.InternalRich) > 0 && plain == richPlain {
		cells = append([]doc.Cell{}, clip.InternalRich...)
	} else {
		cells = doc.TextToCells(plain, m.typingAttrs)
	}
	if len(cells) == 0 {
		return
	}
	m.undo.PushSpan(m.doc, 0, len(m.doc.Lines))
	if m.selStart != nil && m.selEnd != nil {
		m.cursorLine, m.cursorCol = doc.DeleteSelection(m.doc, *m.selStart, *m.selEnd)
		m.selStart, m.selEnd = nil, nil
	}
	m.cursorLine, m.cursorCol = doc.InsertCells(m.doc, m.cursorLine, m.cursorCol, cells)
	m.dirty = true
}

func (m *Model) save() (tea.Model, tea.Cmd) {
	if m.path == "" {
		m.beginSaveAs(false)
		return *m, nil
	}
	if err := docio.SaveDocument(m.doc, m.path); err != nil {
		m.setStatus(i18n.Tr("Error al guardar"))
	} else {
		m.dirty = false
		m.setStatus(fmt.Sprintf(i18n.Tr("Guardado: %s"), filepath.Base(m.path)))
	}
	return *m, nil
}

func (m *Model) beginSaveAs(docx bool) {
	m.mode = modeSaveAs
	m.input.SetValue("")
	m.input.Placeholder = i18n.Tr("Nombre (se guarda en ~/lightwrite/):")
	m.input.Focus()
	_ = docx
}

func (m *Model) beginConfirm(md mode) {
	m.mode = md
	m.input.SetValue("")
	m.input.Focus()
}

func (m *Model) newDoc() {
	m.undo.PushSpan(m.doc, 0, len(m.doc.Lines))
	m.doc = doc.New()
	m.path = ""
	m.cursorLine, m.cursorCol = 0, 0
	m.dirty = false
	m.selStart, m.selEnd = nil, nil
	m.setStatus(i18n.Tr("Nuevo documento"))
}

func (m *Model) openBrowser() {
	start := docio.DocsDir()
	if m.path != "" {
		start = filepath.Dir(m.path)
	}
	if fi, err := os.Stat(start); err != nil || !fi.IsDir() {
		start, _ = os.UserHomeDir()
	}
	m.browseDir = start
	ents, _ := os.ReadDir(start)
	m.browseEntries = filterEntries(ents)
	m.browseIndex = 0
	m.mode = modeBrowse
}

func filterEntries(ents []os.DirEntry) []os.DirEntry {
	var out []os.DirEntry
	for _, e := range ents {
		if e.IsDir() {
			out = append(out, e)
			continue
		}
		ext := strings.ToLower(filepath.Ext(e.Name()))
		switch ext {
		case ".rtf", ".txt", ".docx", ".doc":
			out = append(out, e)
		}
	}
	return out
}

func (m Model) handleBrowse(key string) (tea.Model, tea.Cmd) {
	switch key {
	case "esc":
		m.mode = modeEdit
	case "up":
		if m.browseIndex > 0 {
			m.browseIndex--
		}
	case "down":
		if m.browseIndex < len(m.browseEntries)-1 {
			m.browseIndex++
		}
	case "backspace":
		parent := filepath.Dir(m.browseDir)
		m.browseDir = parent
		ents, _ := os.ReadDir(parent)
		m.browseEntries = filterEntries(ents)
		m.browseIndex = 0
	case "enter":
		if len(m.browseEntries) == 0 {
			return m, nil
		}
		e := m.browseEntries[m.browseIndex]
		full := filepath.Join(m.browseDir, e.Name())
		if e.IsDir() {
			m.browseDir = full
			ents, _ := os.ReadDir(full)
			m.browseEntries = filterEntries(ents)
			m.browseIndex = 0
			return m, nil
		}
		d, err := docio.LoadDocument(full)
		if err != nil {
			m.setStatus(err.Error())
			m.mode = modeEdit
			return m, nil
		}
		m.doc = d
		m.path = full
		m.dirty = false
		m.cursorLine, m.cursorCol = 0, 0
		m.mode = modeEdit
	}
	return m, nil
}

func (m Model) handleConfirm(key string) (tea.Model, tea.Cmd) {
	switch key {
	case "esc", "n":
		m.mode = modeEdit
		m.setStatus(i18n.Tr("Cancelado"))
	case "y", "s", "enter":
		ans := strings.ToLower(strings.TrimSpace(m.input.Value()))
		if key == "enter" && ans != "" && ans != "y" && ans != "s" && ans != "yes" && ans != "si" && ans != "sí" {
			m.mode = modeEdit
			m.setStatus(i18n.Tr("Cancelado"))
			return m, nil
		}
		switch m.mode {
		case modeConfirmQuit:
			m.quitting = true
			return m, tea.Quit
		case modeConfirmNew:
			m.newDoc()
			m.mode = modeEdit
		case modeConfirmOpen:
			m.mode = modeEdit
			m.openBrowser()
		case modeConfirmOverwrite:
			m.path = m.pendingPath
			m.mode = modeEdit
			return m.save()
		}
	default:
		var cmd tea.Cmd
		m.input, cmd = m.input.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune(key)})
		return m, cmd
	}
	return m, nil
}

func (m Model) handleMenu(key string) (tea.Model, tea.Cmd) {
	menus := menuDefs()
	switch key {
	case "esc", "f9":
		m.menuOpen = -1
	case "left":
		m.menuOpen = (m.menuOpen - 1 + len(menus)) % len(menus)
		m.menuSelected = 0
	case "right":
		m.menuOpen = (m.menuOpen + 1) % len(menus)
		m.menuSelected = 0
	case "up":
		if m.menuSelected > 0 {
			m.menuSelected--
		}
	case "down":
		if m.menuSelected < len(menus[m.menuOpen].items)-1 {
			m.menuSelected++
		}
	case "enter":
		action := menus[m.menuOpen].items[m.menuSelected].action
		m.menuOpen = -1
		return m.dispatchAction(action)
	}
	return m, nil
}

func (m Model) dispatchAction(action string) (tea.Model, tea.Cmd) {
	keyMap := map[string]tea.KeyType{
		"ctrl+n": tea.KeyCtrlN,
		"ctrl+o": tea.KeyCtrlO,
		"ctrl+s": tea.KeyCtrlS,
		"ctrl+q": tea.KeyCtrlQ,
		"ctrl+z": tea.KeyCtrlZ,
		"ctrl+x": tea.KeyCtrlX,
		"ctrl+c": tea.KeyCtrlC,
		"ctrl+v": tea.KeyCtrlV,
		"ctrl+f": tea.KeyCtrlF,
		"ctrl+b": tea.KeyCtrlB,
		"ctrl+i": tea.KeyCtrlI,
		"ctrl+u": tea.KeyCtrlU,
		"ctrl+g": tea.KeyCtrlG,
		"ctrl+h": tea.KeyCtrlH,
	}
	if kt, ok := keyMap[action]; ok {
		return m.handleKey(tea.KeyMsg{Type: kt})
	}
	return m, nil
}


func (m Model) submitPrompt() (tea.Model, tea.Cmd) {
	val := m.input.Value()
	m.input.Blur()
	switch m.mode {
	case modeFind:
		m.searchTerm = val
		m.searchMatches = doc.FindAll(m.doc, val)
		m.searchIndex = 0
		m.mode = modeEdit
		if len(m.searchMatches) == 0 {
			m.setStatus(i18n.Tr("No encontrado"))
		} else {
			pos := m.searchMatches[0]
			m.cursorLine, m.cursorCol = pos[0], pos[1]
			m.setStatus(fmt.Sprintf("%d/%d", 1, len(m.searchMatches)))
		}
	case modeReplaceFind:
		m.searchTerm = val
		m.mode = modeReplaceWith
		m.input.SetValue(m.replaceTerm)
		m.input.Placeholder = i18n.Tr("Reemplazar con:")
		m.input.Focus()
		return m, textinput.Blink
	case modeReplaceWith:
		m.replaceTerm = val
		m.undo.PushSpan(m.doc, 0, len(m.doc.Lines))
		n := doc.ReplaceAll(m.doc, m.searchTerm, m.replaceTerm)
		m.dirty = true
		m.mode = modeEdit
		switch n {
		case 0:
			m.setStatus(i18n.Tr("No encontrado"))
		case 1:
			m.setStatus(i18n.Tr("1 reemplazo"))
		default:
			m.setStatus(fmt.Sprintf(i18n.Tr("%d reemplazos"), n))
		}
	case modeSaveAs:
		name := strings.TrimSpace(val)
		m.mode = modeEdit
		if name == "" {
			return m, nil
		}
		full := name
		if !strings.Contains(name, "/") && !strings.HasPrefix(name, "~") {
			full = filepath.Join(docio.DocsDir(), name)
		}
		full = expandHome(full)
		if filepath.Ext(full) == "" {
			full += ".rtf"
		}
		if _, err := os.Stat(full); err == nil {
			m.pendingPath = full
			m.beginConfirm(modeConfirmOverwrite)
			return m, nil
		}
		m.path = full
		return m.save()
	}
	return m, nil
}

func expandHome(p string) string {
	if strings.HasPrefix(p, "~") {
		home, _ := os.UserHomeDir()
		return filepath.Join(home, strings.TrimPrefix(p, "~"))
	}
	return p
}

type menuItem struct {
	label, action string
}
type menu struct {
	title string
	items []menuItem
}

func menuDefs() []menu {
	return []menu{
		{title: "File", items: []menuItem{{"New", "ctrl+n"}, {"Open", "ctrl+o"}, {"Save", "ctrl+s"}, {"Quit", "ctrl+q"}}},
		{title: "Edit", items: []menuItem{{"Undo", "ctrl+z"}, {"Cut", "ctrl+x"}, {"Copy", "ctrl+c"}, {"Paste", "ctrl+v"}, {"Find", "ctrl+f"}}},
		{title: "Format", items: []menuItem{{"Bold", "ctrl+b"}, {"Italic", "ctrl+i"}, {"Underline", "ctrl+u"}}},
		{title: "Help", items: []menuItem{{"Manual", "ctrl+g"}, {"About", "ctrl+h"}}},
	}
}

func textWidth(w int) int {
	tw := doc.TextWidth
	if w-4 < tw {
		tw = max(1, w-4)
	}
	return tw
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

// Styles
var (
	titleStyle  = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("252")).Background(lipgloss.Color("235"))
	menuStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color("245")).Background(lipgloss.Color("236"))
	menuActive  = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("230")).Background(lipgloss.Color("62"))
	statusStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("245")).Background(lipgloss.Color("235"))
	pageStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color("252"))
	selStyle    = lipgloss.NewStyle().Foreground(lipgloss.Color("230")).Background(lipgloss.Color("62"))
	ruleStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color("240"))
	boxStyle    = lipgloss.NewStyle().Border(lipgloss.RoundedBorder()).BorderForeground(lipgloss.Color("62")).Padding(0, 1)
)

func (m Model) View() string {
	if m.width == 0 {
		return "Loading…"
	}
	tw := textWidth(m.width)
	title := "LIGHTWRITE"
	if m.path != "" {
		title += "  ·  " + filepath.Base(m.path)
	}
	if m.dirty {
		title += " *"
	}
	title = titleStyle.Width(m.width).Render(padCenter(title, m.width))

	var menuParts []string
	for i, menu := range menuDefs() {
		st := menuStyle
		if i == m.menuOpen {
			st = menuActive
		}
		menuParts = append(menuParts, st.Render(" "+menu.title+" "))
	}
	menuBar := menuStyle.Width(m.width).Render(strings.Join(menuParts, "│"))

	rule := ruleStyle.Render(strings.Repeat("─", max(1, m.width)))

	bodyH := max(1, m.height-5)
	var body string
	switch m.mode {
	case modeHelp:
		body = renderScrollText(i18n.Manual(), tw, bodyH, m.helpScroll, m.width)
	case modeAbout:
		body = renderScrollText(i18n.About(), tw, bodyH, m.helpScroll, m.width)
	case modeBrowse:
		body = m.renderBrowse(bodyH)
	case modeChapters:
		body = m.renderChapters(bodyH)
	default:
		body = m.renderPage(tw, bodyH)
	}

	statusLeft := fmt.Sprintf(" Words: %d ", m.doc.WordCount())
	statusRight := " " + m.status + " "
	gap := max(1, m.width-lipgloss.Width(statusLeft)-lipgloss.Width(statusRight))
	status := statusStyle.Width(m.width).Render(statusLeft + strings.Repeat(" ", gap) + statusRight)

	prompt := ""
	if m.mode == modeFind || m.mode == modeReplaceFind || m.mode == modeReplaceWith || m.mode == modeSaveAs || m.isConfirm() {
		label := m.promptLabel()
		prompt = "\n" + label + m.input.View()
	}

	dropdown := ""
	if m.menuOpen >= 0 {
		dropdown = "\n" + m.renderDropdown()
	}

	return title + "\n" + rule + "\n" + menuBar + "\n" + rule + "\n" + body + dropdown + prompt + "\n" + rule + "\n" + status
}

func (m Model) promptLabel() string {
	switch m.mode {
	case modeConfirmQuit:
		return i18n.Tr("¿Salir sin guardar? (s/n):")
	case modeConfirmNew:
		return i18n.Tr("¿Descartar cambios? (s/n):")
	case modeConfirmOpen:
		return i18n.Tr("¿Descartar cambios y abrir? (s/n):")
	case modeConfirmOverwrite:
		return fmt.Sprintf(i18n.Tr("¿Sobrescribir %s? (s/n):"), filepath.Base(m.pendingPath))
	default:
		return m.input.Placeholder + " "
	}
}

func (m Model) renderPage(tw, bodyH int) string {
	lines := m.cache.VisualLines(m.doc, tw)
	textX := max(2, (m.width-tw)/2)
	pad := strings.Repeat(" ", textX)
	var rows []string
	end := min(len(lines), m.scrollRow+bodyH)
	for i := m.scrollRow; i < end; i++ {
		vl := lines[i]
		text := vl.Text
		if text == doc.PageBreak {
			text = "— page break —"
		}
		styled := pageStyle.Render(text)
		// cursor marker
		if vl.LineIndex == m.cursorLine {
			rel := m.cursorCol - vl.Start
			runes := []rune(vl.Text)
			if rel >= 0 && rel <= len(runes) {
				left := string(runes[:min(rel, len(runes))])
				right := ""
				cur := " "
				if rel < len(runes) {
					cur = string(runes[rel])
					right = string(runes[rel+1:])
				}
				styled = pageStyle.Render(left) +
					lipgloss.NewStyle().Reverse(true).Render(cur) +
					pageStyle.Render(right)
			}
		}
		rows = append(rows, pad+styled)
	}
	for len(rows) < bodyH {
		rows = append(rows, "")
	}
	return strings.Join(rows, "\n")
}

func (m Model) renderBrowse(bodyH int) string {
	var b strings.Builder
	b.WriteString(boxStyle.Width(min(m.width-4, 60)).Render(
		fmt.Sprintf("Open\n%s\n%s", m.browseDir, strings.Repeat("─", 40)),
	))
	b.WriteString("\n")
	for i, e := range m.browseEntries {
		if i >= bodyH-3 {
			break
		}
		name := e.Name()
		if e.IsDir() {
			name += "/"
		}
		line := "  " + name
		if i == m.browseIndex {
			line = selStyle.Render("> " + name)
		}
		b.WriteString(line + "\n")
	}
	return b.String()
}

func (m Model) renderChapters(bodyH int) string {
	heads := doc.CollectHeadings(m.doc)
	var lines []string
	lines = append(lines, boxStyle.Render("Chapter map"))
	if len(heads) == 0 {
		lines = append(lines, "  (no chapters)")
	}
	for _, h := range heads {
		lines = append(lines, fmt.Sprintf("  H%d  %s", h.Level, h.Title))
	}
	lines = append(lines, "", "  Esc to close")
	return strings.Join(lines[:min(len(lines), bodyH)], "\n")
}

func (m Model) renderDropdown() string {
	menus := menuDefs()
	if m.menuOpen < 0 || m.menuOpen >= len(menus) {
		return ""
	}
	var lines []string
	for i, it := range menus[m.menuOpen].items {
		line := " " + it.label + " "
		if i == m.menuSelected {
			line = menuActive.Render(line)
		} else {
			line = menuStyle.Render(line)
		}
		lines = append(lines, line)
	}
	return strings.Join(lines, "\n")
}

func renderScrollText(text string, tw, bodyH, scroll, width int) string {
	paras := strings.Split(text, "\n")
	var wrapped []string
	for _, p := range paras {
		if p == "" {
			wrapped = append(wrapped, "")
			continue
		}
		runes := []rune(p)
		for len(runes) > tw {
			wrapped = append(wrapped, string(runes[:tw]))
			runes = runes[tw:]
		}
		wrapped = append(wrapped, string(runes))
	}
	if scroll > len(wrapped) {
		scroll = max(0, len(wrapped)-1)
	}
	end := min(len(wrapped), scroll+bodyH)
	pad := strings.Repeat(" ", max(2, (width-tw)/2))
	var rows []string
	for _, row := range wrapped[scroll:end] {
		rows = append(rows, pad+pageStyle.Render(row))
	}
	return strings.Join(rows, "\n")
}

func padCenter(s string, w int) string {
	n := lipgloss.Width(s)
	if n >= w {
		return s
	}
	left := (w - n) / 2
	return strings.Repeat(" ", left) + s + strings.Repeat(" ", w-n-left)
}

func Run(path string) error {
	m, err := New(path)
	if err != nil {
		return err
	}
	p := tea.NewProgram(m, tea.WithAltScreen(), tea.WithMouseAllMotion())
	_, err = p.Run()
	return err
}
