;;; biblegateway-export.el --- Insert Bible passages in a selected format -*- lexical-binding: t; -*-

;; Package-Requires: ((emacs "27.1"))
;; Version: 2.3.0
;; Keywords: text, tools

;;; Commentary:
;; Load this file and run M-x biblegateway-export-insert in a writable buffer.
;; Requires Python and the complete biblegateway-export project.

;;; Code:

(require 'org)
(require 'subr-x)

(defgroup biblegateway-export nil
  "Fetch BibleGateway passages as Org, Markdown, or plain text."
  :group 'org)

(defcustom biblegateway-export-script
  (expand-file-name "~/devel/biblegateway-export/bg-export")
  "Path to bg-export.
Keep the biblegateway_export package directory beside the script."
  :type 'file)

(defcustom biblegateway-export-python-program "python3"
  "Python executable, either an absolute filename or a name in `exec-path'."
  :type 'string)

(defcustom biblegateway-export-translation "NET"
  "Default BibleGateway translation abbreviation."
  :type 'string)

(defcustom biblegateway-export-extra-arguments '("-c" "-e" "-f" "-r")
  "Additional bg-export arguments used for Emacs lookups.
The default excludes copyright notices, editorial headings, footnotes, and
cross-references.  Set to nil to include these elements.  Use a list of
individual arguments, not a shell command string."
  :type '(repeat string))

(defcustom biblegateway-export-default-format "auto"
  "Default format offered by `biblegateway-export-insert'.
With auto, offer Org in Org buffers, Markdown in Markdown buffers, and TXT
elsewhere.  The interactive command always lets you choose another format."
  :type '(choice (const :tag "Choose from buffer mode" "auto")
                 (const :tag "Org" "org")
                 (const :tag "Markdown" "md")
                 (const :tag "Plain text" "txt")))

(defvar biblegateway-export-reference-history nil
  "Previously requested Bible passages.")
(defvar biblegateway-export-translation-history nil
  "Previously requested Bible versions.")
(defvar biblegateway-export-format-history nil
  "Previously selected output formats.")

(defun biblegateway-export--default-format ()
  "Return the default format name for the current buffer."
  (if (equal biblegateway-export-default-format "auto")
      (cond ((derived-mode-p 'org-mode) "org")
            ((derived-mode-p 'markdown-mode) "md")
            (t "txt"))
    (if (equal biblegateway-export-default-format "markdown")
        "md"
      biblegateway-export-default-format)))

(defun biblegateway-export--normalize-format (output-format)
  "Validate OUTPUT-FORMAT and return its canonical CLI name."
  (pcase output-format
    ((or "md" "markdown") "markdown")
    ((or "org" "txt") output-format)
    (_ (user-error "Choose org, md (markdown), or txt"))))

(defun biblegateway-export--read-arguments ()
  "Prompt for a reference, translation, and output format."
  (list (read-string "Bible passage: " nil
                     'biblegateway-export-reference-history)
        (completing-read
         "Bible version: "
         '("NET" "NIV" "NIVUK" "ESV" "NLT" "KJV" "NKJV" "NASB"
           "NRSVUE" "CSB" "LEB" "MSG" "WEB")
         nil nil nil 'biblegateway-export-translation-history
         biblegateway-export-translation)
        (completing-read "Output format: " '("org" "md" "txt")
                         nil t nil 'biblegateway-export-format-history
                         (biblegateway-export--default-format))))

(defun biblegateway-export--result-mode (output-format)
  "Select a mode for a preserved result in OUTPUT-FORMAT."
  (cond ((equal output-format "org") (org-mode))
        ((and (equal output-format "markdown") (fboundp 'markdown-mode))
         (markdown-mode))
        (t (text-mode))))

(defcustom biblegateway-export-heading-level nil
  "Level for the passage heading, or nil for a child of the current heading.
With nil, use level 1 before the first heading; otherwise use a child level."
  :type '(choice (const :tag "Child of current heading" nil)
                 (integer :tag "Fixed heading level")))

(defun biblegateway-export--prepare (text level namespace)
  "Prepare Org TEXT for insertion at heading LEVEL with footnote NAMESPACE."
  (with-temp-buffer
    (insert text)
    (goto-char (point-min))
    (while (re-search-forward "^\\(\\*+\\) " nil t)
      (replace-match (concat (make-string (+ (length (match-string 1))
                                             (1- level)) ?*) " ") t t))
    (goto-char (point-min))
    ;; References and definitions both use [fn:LABEL].  Namespace each lookup
    ;; so repeated passages do not share unrelated a/b/A/B definitions.
    (while (re-search-forward "\\[fn:\\([[:alnum:]]+\\)\\]" nil t)
      (replace-match (concat "[fn:" namespace "-" (match-string 1) "]") t t))
    (buffer-string)))

(defun biblegateway-export--finish (process output errors marker level namespace output-format)
  "Handle completed PROCESS with OUTPUT and ERRORS at MARKER.
LEVEL and NAMESPACE control Org insertion; OUTPUT-FORMAT selects syntax."
  (when (and (memq (process-status process) '(exit signal))
             (not (process-get process 'biblegateway-export-finished)))
    (process-put process 'biblegateway-export-finished t)
    (let ((text (when (buffer-live-p output)
                  (with-current-buffer output (buffer-string)))))
      (unwind-protect
          (if (and (eq (process-status process) 'exit)
                   (zerop (process-exit-status process))
                   text (not (string-empty-p (string-trim text))))
              (condition-case err
                  (progn
                    (unless (marker-buffer marker)
                      (error "The destination buffer was closed"))
                    (with-current-buffer (marker-buffer marker)
                      (save-excursion
                        (goto-char marker)
                        (atomic-change-group
                          (unless (bolp) (insert "\n"))
                          (insert (if (equal output-format "org")
                                      (biblegateway-export--prepare text level namespace)
                                    text))
                          (unless (bolp) (insert "\n")))))
                    (kill-buffer output)
                    (message "BibleGateway passage inserted"))
                (error
                 ;; Preserve fetched text if the destination became read-only,
                 ;; was closed, or another insertion error occurred.
                 (with-current-buffer output
                   (biblegateway-export--result-mode output-format))
                 (display-buffer output)
                 (message "Could not insert passage: %s; result is in %s"
                          (error-message-string err) (buffer-name output))))
            (when (buffer-live-p output)
              (with-current-buffer output
                (goto-char (point-max))
                (insert (format "\nBibleGateway export failed (status %s).\n"
                                (process-exit-status process)))
                (when (buffer-live-p errors)
                  (insert-buffer-substring errors))
                (special-mode))
              (display-buffer output))
            (message "BibleGateway export failed; see the result buffer"))
        (set-marker marker nil)
        (when (buffer-live-p errors) (kill-buffer errors))))))

;;;###autoload
(defun biblegateway-export-insert (reference translation &optional output-format)
  "Fetch REFERENCE in TRANSLATION and insert OUTPUT-FORMAT asynchronously.
Prompt for all three values when called interactively.  OUTPUT-FORMAT can be
org, md (or markdown), or txt.  If omitted, use the configured buffer default.
Only Org output receives heading adjustment and unique footnote labels.
The marker follows edits while fetching.  Do not replace selected text or
change the destination buffer's mode.  Clipboard copying is disabled."
  (interactive (biblegateway-export--read-arguments))
  (barf-if-buffer-read-only)
  (when (or (string-empty-p (string-trim reference))
            (string-empty-p (string-trim translation)))
    (user-error "Passage and translation must not be empty"))
  (setq output-format
        (biblegateway-export--normalize-format
         (or output-format (biblegateway-export--default-format))))
  (unless (file-readable-p biblegateway-export-script)
    (user-error "Cannot read bg-export: set biblegateway-export-script"))
  (let ((python (executable-find biblegateway-export-python-program))
        (level (if (equal output-format "org")
                   (or biblegateway-export-heading-level
                       (if (derived-mode-p 'org-mode)
                           (1+ (or (org-current-level) 0))
                         1))
                 1)))
    (unless python
      (user-error "Cannot find Python: set biblegateway-export-python-program"))
    (unless (and (integerp level) (> level 0))
      (user-error "Heading level must be a positive integer"))
    (let ((marker (copy-marker (point)))
          (namespace (concat "bg-" (substring
                                   (secure-hash 'sha1
                                                (format "%s-%s-%s" (current-time)
                                                        (random) reference)) 0 12)))
          (output (generate-new-buffer "*BibleGateway result*"))
          (errors (generate-new-buffer " *BibleGateway stderr*")))
      (condition-case err
          (prog1
              (make-process
               :name "biblegateway-export"
               :buffer output :stderr errors :noquery t
               :connection-type 'pipe :coding 'utf-8-unix
               ;; Argument list, never a shell command: punctuation in the
               ;; passage cannot be interpreted by a shell.
               :command (append
                         (list python (expand-file-name biblegateway-export-script))
                         biblegateway-export-extra-arguments
                         (list "--no-clipboard" "--format" output-format
                               "--version" translation "--" reference))
               :sentinel (lambda (process _event)
                           (biblegateway-export--finish
                            process output errors marker level namespace output-format)))
            (message "Fetching %s (%s, %s)..." reference translation output-format))
        (error
         (set-marker marker nil)
         (kill-buffer output)
         (kill-buffer errors)
         (signal (car err) (cdr err)))))))

(provide 'biblegateway-export)
;;; biblegateway-export.el ends here
