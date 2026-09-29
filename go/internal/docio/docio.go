package docio

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/magiccityreader/Lightwrite/internal/doc"
	"github.com/magiccityreader/Lightwrite/internal/rtf"
)

func ConfigDir() string {
	home, _ := os.UserHomeDir()
	return filepath.Join(home, ".config", "lightwrite")
}

func DocsDir() string {
	home, _ := os.UserHomeDir()
	return filepath.Join(home, "lightwrite")
}

func SessionRTF() string {
	return filepath.Join(ConfigDir(), "session.rtf")
}

func EnsureDirs() error {
	if err := os.MkdirAll(ConfigDir(), 0o755); err != nil {
		return err
	}
	return os.MkdirAll(DocsDir(), 0o755)
}

func LoadDocument(path string) (*doc.Document, error) {
	ext := strings.ToLower(filepath.Ext(path))
	switch ext {
	case ".rtf":
		return rtf.Load(path)
	case ".txt", "":
		b, err := os.ReadFile(path)
		if err != nil {
			return nil, err
		}
		d := doc.New()
		lines := strings.Split(strings.ReplaceAll(string(b), "\r\n", "\n"), "\n")
		d.Lines = lines
		d.Format = make([][]doc.Attr, len(lines))
		d.Aligns = make([]doc.Align, len(lines))
		for i, ln := range lines {
			d.Format[i] = make([]doc.Attr, len([]rune(ln)))
			d.Aligns[i] = doc.AlignLeft
		}
		return d, nil
	case ".docx", ".doc":
		tmp, err := os.MkdirTemp("", "lightwrite-in-*")
		if err != nil {
			return nil, err
		}
		defer os.RemoveAll(tmp)
		out, err := ConvertWithLibreOffice(path, "rtf", tmp)
		if err != nil {
			return nil, err
		}
		return rtf.Load(out)
	default:
		return rtf.Load(path)
	}
}

func SaveDocument(d *doc.Document, path string) error {
	ext := strings.ToLower(filepath.Ext(path))
	switch ext {
	case ".txt":
		return os.WriteFile(path, []byte(d.String()), 0o644)
	case ".docx", ".doc":
		return fmt.Errorf("use StartDocxSave for docx")
	default:
		if ext == "" {
			path += ".rtf"
		}
		return rtf.Save(d, path)
	}
}

func filesystemDirs(paths ...string) []string {
	seen := map[string]bool{}
	var dirs []string
	for _, p := range paths {
		if p == "" {
			continue
		}
		abs, _ := filepath.Abs(p)
		dir := abs
		if fi, err := os.Stat(abs); err != nil || !fi.IsDir() {
			dir = filepath.Dir(abs)
		}
		if dir == "" || seen[dir] {
			continue
		}
		seen[dir] = true
		dirs = append(dirs, dir)
	}
	return dirs
}

func FindLibreOffice(extraPaths ...string) []string {
	if p, err := exec.LookPath("soffice"); err == nil {
		return []string{p}
	}
	if p, err := exec.LookPath("libreoffice"); err == nil {
		return []string{p}
	}
	if _, err := exec.LookPath("flatpak"); err == nil {
		cmd := exec.Command("flatpak", "info", "org.libreoffice.LibreOffice")
		if cmd.Run() == nil {
			args := []string{"flatpak", "run", "--filesystem=/tmp"}
			for _, d := range filesystemDirs(extraPaths...) {
				args = append(args, "--filesystem="+d)
			}
			args = append(args, "org.libreoffice.LibreOffice")
			return args
		}
	}
	return nil
}

func ConvertWithLibreOffice(inputPath, outputExt, outputDir string) (string, error) {
	cmdBase := FindLibreOffice(inputPath, outputDir)
	if cmdBase == nil {
		return "", fmt.Errorf("LibreOffice not found")
	}
	if outputDir == "" {
		outputDir = filepath.Dir(inputPath)
	}
	args := append(cmdBase[1:], "--headless", "--convert-to", outputExt, "--outdir", outputDir, inputPath)
	cmd := exec.Command(cmdBase[0], args...)
	if out, err := cmd.CombinedOutput(); err != nil {
		return "", fmt.Errorf("libreoffice: %v (%s)", err, string(out))
	}
	base := strings.TrimSuffix(filepath.Base(inputPath), filepath.Ext(inputPath))
	return filepath.Join(outputDir, base+"."+outputExt), nil
}

type ExportJob struct {
	Proc    *exec.Cmd
	OutPath string
	TmpDir  string
	Kind    string
	Done    chan error
}

func StartPDFExport(d *doc.Document, dest string) (*ExportJob, error) {
	return startConvert(d, dest, "pdf")
}

func StartDocxSave(d *doc.Document, dest string) (*ExportJob, error) {
	return startConvert(d, dest, "docx")
}

func startConvert(d *doc.Document, dest, kind string) (*ExportJob, error) {
	tmp, err := os.MkdirTemp("", "lightwrite-export-*")
	if err != nil {
		return nil, err
	}
	rtfPath := filepath.Join(tmp, "doc.rtf")
	if err := rtf.Save(d, rtfPath); err != nil {
		os.RemoveAll(tmp)
		return nil, err
	}
	cmdBase := FindLibreOffice(rtfPath, dest, tmp)
	if cmdBase == nil {
		os.RemoveAll(tmp)
		return nil, fmt.Errorf("LibreOffice not found")
	}
	outDir := filepath.Dir(dest)
	args := append(cmdBase[1:], "--headless", "--convert-to", kind, "--outdir", tmp, rtfPath)
	cmd := exec.Command(cmdBase[0], args...)
	job := &ExportJob{Proc: cmd, OutPath: dest, TmpDir: tmp, Kind: kind, Done: make(chan error, 1)}
	go func() {
		err := cmd.Run()
		if err == nil {
			produced := filepath.Join(tmp, "doc."+kind)
			if _, e := os.Stat(produced); e == nil {
				_ = os.MkdirAll(outDir, 0o755)
				err = copyFile(produced, dest)
			} else {
				err = fmt.Errorf("output missing")
			}
		}
		os.RemoveAll(tmp)
		job.Done <- err
	}()
	return job, nil
}

func PollExport(job *ExportJob) (done, success bool, message string) {
	select {
	case err := <-job.Done:
		if err != nil {
			return true, false, err.Error()
		}
		return true, true, "Exported: " + filepath.Base(job.OutPath)
	default:
		time.Sleep(0)
		return false, false, ""
	}
}

func copyFile(src, dst string) error {
	b, err := os.ReadFile(src)
	if err != nil {
		return err
	}
	return os.WriteFile(dst, b, 0o644)
}

func ListDirectory(dir string) ([]os.DirEntry, error) {
	return os.ReadDir(dir)
}
