package i18n

import (
	"embed"
	"os"
	"path/filepath"
	"strings"
	"sync"
)

//go:embed locale/*.txt
var localeFS embed.FS

var (
	mu       sync.RWMutex
	lang     = "en"
	fallback = map[string]string{
		"Nuevo documento":                      "New document",
		"Guardado: %s":                         "Saved: %s",
		"Error al guardar":                     "Error saving",
		"Cancelado":                            "Cancelled",
		"Deshecho":                             "Undone",
		"Nada que deshacer":                    "Nothing to undo",
		"No encontrado":                        "Not found",
		"1 reemplazo":                          "1 replacement",
		"%d reemplazos":                        "%d replacements",
		"¿Salir sin guardar? (s/n):":           "Quit without saving? (y/n):",
		"¿Descartar cambios? (s/n):":           "Discard changes? (y/n):",
		"¿Descartar cambios y abrir? (s/n):":   "Discard changes and open? (y/n):",
		"¿Sobrescribir %s? (s/n):":             "Overwrite %s? (y/n):",
		"Nombre (se guarda en ~/lightwrite/):": "Name (saved in ~/lightwrite/):",
		"Reemplazar con:":                      "Replace with:",
		"Copiado":                              "Copied",
		"Cortado":                              "Cut",
		"Manual de Lightwrite":                 "Lightwrite Manual",
		"Acerca de":                            "About",
		"hunspell no instalado":                "hunspell not installed",
		"Ortografía activada":                  "Spell check on",
		"Ortografía desactivada":               "Spell check off",
		"Salto de página":                      "Page break",
		"Seleccionado todo: %d líneas · %d palabras": "Selected all: %d lines · %d words",
	}
	manual = map[string]string{}
	about  = map[string]string{}
)

func init() {
	loadEmbedded()
	detectLang()
}

func loadEmbedded() {
	for _, code := range []string{"en", "es"} {
		if b, err := localeFS.ReadFile("locale/manual." + code + ".txt"); err == nil {
			manual[code] = string(b)
		}
		if b, err := localeFS.ReadFile("locale/about." + code + ".txt"); err == nil {
			about[code] = string(b)
		}
	}
}

func detectLang() {
	if v := os.Getenv("LIGHTWRITE_LANG"); v != "" {
		lang = normalize(v)
		return
	}
	home, _ := os.UserHomeDir()
	b, err := os.ReadFile(filepath.Join(home, ".config", "lightwrite", "language"))
	if err == nil {
		lang = normalize(string(b))
		return
	}
	if v := os.Getenv("LANG"); strings.HasPrefix(strings.ToLower(v), "es") {
		lang = "es"
	}
}

func normalize(s string) string {
	s = strings.TrimSpace(strings.ToLower(s))
	if strings.HasPrefix(s, "es") {
		return "es"
	}
	return "en"
}

func Lang() string {
	mu.RLock()
	defer mu.RUnlock()
	return lang
}

func SetLang(code string) {
	mu.Lock()
	lang = normalize(code)
	mu.Unlock()
	home, _ := os.UserHomeDir()
	dir := filepath.Join(home, ".config", "lightwrite")
	_ = os.MkdirAll(dir, 0o755)
	_ = os.WriteFile(filepath.Join(dir, "language"), []byte(lang), 0o644)
}

func Tr(s string) string {
	mu.RLock()
	l := lang
	mu.RUnlock()
	if l == "es" {
		return s
	}
	if t, ok := fallback[s]; ok {
		return t
	}
	return s
}

func Manual() string {
	mu.RLock()
	l := lang
	mu.RUnlock()
	if t, ok := manual[l]; ok {
		return t
	}
	return manual["en"]
}

func About() string {
	mu.RLock()
	l := lang
	mu.RUnlock()
	if t, ok := about[l]; ok {
		return t
	}
	return about["en"]
}
