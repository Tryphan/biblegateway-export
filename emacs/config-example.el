;;; config-example.el --- Example configuration for your Emacs init

(add-to-list 'load-path
             (expand-file-name "~/devel/biblegateway-export/emacs"))
(require 'biblegateway-export)

(setq biblegateway-export-script
      (expand-file-name "~/devel/biblegateway-export/bg-export")
      biblegateway-export-python-program "/usr/bin/python"
      biblegateway-export-translation "NET"
      biblegateway-export-default-format "auto"
      biblegateway-export-extra-arguments '("-c" "-e" "-f" "-r"))

;; Optional Org buffer key binding.  Choose a different key if already in use.
(define-key org-mode-map (kbd "C-c b") #'biblegateway-export-insert)
