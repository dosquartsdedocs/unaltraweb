# frozen_string_literal: true

require_relative "lib/unaltraweb/version"
require "shellwords"

Gem::Specification.new do |spec|
  spec.name = "unaltraweb"
  spec.version = Unaltraweb::VERSION
  spec.authors = ["dosquartsdedocs"]
  spec.email = [""]

  spec.summary = "Reusable Jekyll core for academic and research websites."
  spec.homepage = "https://github.com/dosquartsdedocs/unaltraweb"
  spec.license = "MIT"
  spec.required_ruby_version = ">= 3.1"

  repo_root = File.expand_path(__dir__)
  tracked_files = `git -c safe.directory=#{repo_root.shellescape} ls-files -z`.split("\x0")
  if tracked_files.empty?
    tracked_files = Dir.chdir(repo_root) do
      Dir.glob("{_includes,_layouts,_sass,_plugins,assets,lib,scripts,docs}/**/*", File::FNM_DOTMATCH).reject do |file|
        File.directory?(file)
      end
    end
  end
  spec.files = tracked_files.select do |file|
    ["_config.yml", "requirements.txt"].include?(file) ||
      file.match?(%r{\A(_includes|_layouts|_sass|_plugins|assets|lib|scripts)/}) ||
      file.match?(%r{\A(README|LICENSE|docs)/})
  end

  spec.require_paths = ["lib"]

  spec.add_runtime_dependency "classifier-reborn"
  spec.add_runtime_dependency "css_parser"
  spec.add_runtime_dependency "feedjira"
  spec.add_runtime_dependency "httparty"
  spec.add_runtime_dependency "jekyll", ">= 4.3", "< 5.0"
  spec.add_runtime_dependency "jekyll-3rd-party-libraries"
  spec.add_runtime_dependency "jekyll-archives-v2"
  spec.add_runtime_dependency "jekyll-cache-bust"
  spec.add_runtime_dependency "jekyll-email-protect"
  spec.add_runtime_dependency "jekyll-feed"
  spec.add_runtime_dependency "jekyll-get-json"
  spec.add_runtime_dependency "jekyll-imagemagick"
  spec.add_runtime_dependency "jekyll-jupyter-notebook"
  spec.add_runtime_dependency "jekyll-link-attributes"
  spec.add_runtime_dependency "jekyll-minifier"
  spec.add_runtime_dependency "jekyll-paginate-v2"
  spec.add_runtime_dependency "jekyll-regex-replace"
  spec.add_runtime_dependency "jekyll-scholar"
  spec.add_runtime_dependency "jekyll-sitemap"
  spec.add_runtime_dependency "jekyll-socials"
  spec.add_runtime_dependency "jekyll-tabs"
  spec.add_runtime_dependency "jekyll-toc"
  spec.add_runtime_dependency "jekyll-twitter-plugin"
  spec.add_runtime_dependency "jemoji"
  spec.add_runtime_dependency "observer"
  spec.add_runtime_dependency "ostruct"
end
