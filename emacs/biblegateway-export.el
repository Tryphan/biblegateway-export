;;; biblegateway-export.el --- Insert Bible passages as Org -*- lexical-binding: t; -*-

;; Package-Requires: ((emacs "27.1"))
;; Version: 2.1.0
;; Keywords: text, tools

;;; Commentary:
;; Load this file and run M-x biblegateway-export-insert in an Org buffer.
;; Requires Python and the complete biblegateway-export project.

;;; Code:

(require 'org)
(require 'subr-x)

(defgroup biblegateway-export nil
  "Fetch BibleGateway passages as Org."
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

(defun biblegateway-export--finish (process output errors marker level namespace)
  "Handle completed PROCESS with OUTPUT and ERRORS at MARKER.
LEVEL and NAMESPACE control insertion formatting."
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
                          (insert (biblegateway-export--prepare text level namespace))
                          (unless (bolp) (insert "\n")))))
                    (kill-buffer output)
                    (message "BibleGateway passage inserted"))
                (error
                 ;; Preserve fetched text if the destination became read-only,
                 ;; was closed, or another insertion error occurred.
                 (with-current-buffer output (org-mode))
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
(defun biblegateway-export-insert (reference translation)
  "Fetch REFERENCE in TRANSLATION asynchronously and insert Org at point.
Prompt for a passage and BibleGateway translation abbreviation.  Insert under
this heading by default.  The insertion marker follows edits while fetching.
Do not replace selected text.  Clipboard copying is disabled."
  (interactive
   (list (read-string "Bible passage: ")
         (read-string "Translation: " nil nil biblegateway-export-translation)))
  (unless (derived-mode-p 'org-mode)
    (user-error "Run this command in an Org buffer"))
  (barf-if-buffer-read-only)
  (when (or (string-empty-p (string-trim reference))
            (string-empty-p (string-trim translation)))
    (user-error "Passage and translation must not be empty"))
  (unless (file-readable-p biblegateway-export-script)
    (user-error "Cannot read bg-export: set biblegateway-export-script"))
  (let ((python (executable-find biblegateway-export-python-program))
        (level (or biblegateway-export-heading-level
                   (1+ (or (org-current-level) 0)))))
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
               :command (list python (expand-file-name biblegateway-export-script)
                              "--no-clipboard" "--format" "org"
                              "--version" translation "--" reference)
               :sentinel (lambda (process _event)
                           (biblegateway-export--finish
                            process output errors marker level namespace)))
            (message "Fetching %s (%s)..." reference translation))
        (error
         (set-marker marker nil)
         (kill-buffer output)
         (kill-buffer errors)
         (signal (car err) (cdr err)))))))

(provide 'biblegateway-export)
;;; biblegateway-export.el ends here
