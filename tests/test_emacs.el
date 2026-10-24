;;; test_emacs.el --- Offline integration tests -*- lexical-binding: t; -*-
(require 'ert)
(require 'cl-lib)
(require 'biblegateway-export)

(defun biblegateway-export-test--wait (process)
  "Wait up to five seconds for PROCESS and its sentinel."
  (let ((deadline (+ (float-time) 5)))
    (while (and (not (process-get process 'biblegateway-export-finished))
                (< (float-time) deadline))
      (accept-process-output nil 0.05))
    (should (process-get process 'biblegateway-export-finished))
    (should-not (process-live-p process))))

(defmacro biblegateway-export-test--with-script (body &rest forms)
  "Run FORMS with a temporary exporter containing shell BODY."
  (declare (indent 1))
  `(let* ((script (make-temp-file "bg-export-test-" nil ".sh" ,body))
          (biblegateway-export-script script)
          (biblegateway-export-python-program "sh")
          (biblegateway-export-heading-level nil)
          (original-buffers (buffer-list)))
     (unwind-protect
         (progn ,@forms)
       (delete-file script)
       (dolist (buffer (buffer-list))
         (unless (memq buffer original-buffers)
           (when (buffer-live-p buffer) (kill-buffer buffer)))))))

(ert-deftest biblegateway-export-prepare-heading-and-notes ()
  (should (equal (biblegateway-export--prepare
                  "* Passage\n** Heading\nText [fn:a][fn:A]\n[fn:a] Note\n[fn:A] Ref\n"
                  3 "unique")
                 "*** Passage\n**** Heading\nText [fn:unique-a][fn:unique-A]\n[fn:unique-a] Note\n[fn:unique-A] Ref\n")))

(ert-deftest biblegateway-export-async-insertion-and-marker ()
  (biblegateway-export-test--with-script
      "sleep 0.1\nprintf '%s\\n' '* Sample' 'Text [fn:a]' '[fn:a] Note'\n"
    (with-temp-buffer
      (org-mode)
      (insert "* Study\n")
      (let ((process (biblegateway-export-insert "John 3:16" "NET")))
        ;; Edits before the insertion position must move the marker.
        (goto-char (point-min))
        (insert "#+title: Test\n")
        (biblegateway-export-test--wait process))
      (should (string-prefix-p "#+title: Test\n* Study\n** Sample\n" (buffer-string)))
      (should (string-match-p "\\[fn:bg-[[:xdigit:]]+-a\\]" (buffer-string)))
      (should-not (string-match-p "\\[fn:a\\]" (buffer-string))))))

(ert-deftest biblegateway-export-passes-arguments-without-shell ()
  (biblegateway-export-test--with-script "printf '%s\\n' '* Sample'\n"
    (with-temp-buffer
      (org-mode)
      (let* ((real-make-process (symbol-function 'make-process))
             (reference "John 3:16; $(echo unwanted)")
             captured)
        (cl-letf (((symbol-function 'make-process)
                   (lambda (&rest args)
                     (setq captured (plist-get args :command))
                     (apply real-make-process args))))
          (biblegateway-export-test--wait
           (biblegateway-export-insert reference "NIV")))
        (should (equal (cddr captured)
                       (list "--no-clipboard" "--format" "org"
                             "--version" "NIV" "--" reference)))))))

(ert-deftest biblegateway-export-failure-does-not-insert ()
  (biblegateway-export-test--with-script
      "printf '%s\\n' 'Network failure' >&2\nexit 7\n"
    (with-temp-buffer
      (org-mode)
      (insert "Existing text\n")
      (biblegateway-export-test--wait
       (biblegateway-export-insert "John 3:16" "NET"))
      (should (equal (buffer-string) "Existing text\n"))
      (should (cl-some (lambda (buffer)
                         (with-current-buffer buffer
                           (string-match-p "Network failure" (buffer-string))))
                       (buffer-list))))))

(ert-deftest biblegateway-export-read-only-keeps-result ()
  (biblegateway-export-test--with-script
      "sleep 0.1\nprintf '%s\\n' '* Sample' 'Fetched passage'\n"
    (with-temp-buffer
      (org-mode)
      (let ((process (biblegateway-export-insert "John 3:16" "NET")))
        (setq buffer-read-only t)
        (biblegateway-export-test--wait process)
        (should (string-empty-p (buffer-string)))
        (should (buffer-live-p (process-buffer process)))
        (should (string-match-p "Fetched passage"
                                (with-current-buffer (process-buffer process)
                                  (buffer-string))))))))

(ert-deftest biblegateway-export-rejects-non-org-buffer ()
  (with-temp-buffer
    (should-error (biblegateway-export-insert "John 3:16" "NET")
                  :type 'user-error)))

(ert-deftest biblegateway-export-fixed-top-level ()
  (biblegateway-export-test--with-script "printf '%s\\n' '* Sample'\n"
    (with-temp-buffer
      (org-mode)
      (insert "* Study\n** Subheading\n")
      (let ((biblegateway-export-heading-level 1))
        (biblegateway-export-test--wait
         (biblegateway-export-insert "John 3:16" "NET")))
      (should (string-suffix-p "\n* Sample\n" (buffer-string))))))

(ert-deftest biblegateway-export-closed-target-keeps-result ()
  (biblegateway-export-test--with-script
      "sleep 0.1\nprintf '%s\\n' '* Sample' 'Fetched passage'\n"
    (let* ((target (generate-new-buffer " *bg-test-target*"))
           (process (with-current-buffer target
                      (org-mode)
                      (biblegateway-export-insert "John 3:16" "NET"))))
      (kill-buffer target)
      (biblegateway-export-test--wait process)
      (should (buffer-live-p (process-buffer process)))
      (should (string-match-p "Fetched passage"
                              (with-current-buffer (process-buffer process)
                                (buffer-string)))))))

(ert-deftest biblegateway-export-empty-success-does-not-insert ()
  (biblegateway-export-test--with-script "exit 0\n"
    (with-temp-buffer
      (org-mode)
      (insert "Existing text\n")
      (biblegateway-export-test--wait
       (biblegateway-export-insert "John 3:16" "NET"))
      (should (equal (buffer-string) "Existing text\n")))))

(defconst biblegateway-export-test--root
  (file-name-directory
   (directory-file-name (file-name-directory (or load-file-name buffer-file-name)))))

(ert-deftest biblegateway-export-real-python-exporter ()
  "Exercise Emacs -> Python CLI -> HTML parser -> Org insertion offline."
  (let* ((fixture (expand-file-name "tests/fixtures/passage.fixture"
                                    biblegateway-export-test--root))
         (script (make-temp-file
                  "bg-real-export-" nil ".py"
                  (format
                   (concat "import sys\nsys.path.insert(0, %S)\n"
                           "from biblegateway_export.cli import main\n"
                           "raise SystemExit(main(['--test', %S] + sys.argv[1:]))\n")
                   biblegateway-export-test--root fixture)))
         (biblegateway-export-script script)
         (biblegateway-export-python-program (or (getenv "BG_TEST_PYTHON") "python3")))
    (unwind-protect
        (with-temp-buffer
          (org-mode)
          (insert "* Study\n")
          (biblegateway-export-test--wait
           (biblegateway-export-insert "Sample 1" "NET"))
          (should (string-match-p "^\\*\\* Sample 1:1-12 (TEST)" (buffer-string)))
          (should (string-match-p "\\[fn:bg-[[:xdigit:]]+-a\\]" (buffer-string)))
          (should (string-match-p "/supplied words/" (buffer-string))))
      (delete-file script))))
