# frozen_string_literal: true

require "fileutils"
require "open3"
require "shellwords"

# Rewrites Markdown and HTML image references from diagram text sources to SVGs.
# If an edited SVG exists next to the source, it wins over the generated one.
module Unaltraweb
  module MermaidMmdImages
    module_function

    BASEURL_PREFIX = /\A\{\{\s*site\.baseurl\s*\}\}/.freeze
    REMOTE_PATH_PREFIX = %r{\A(?:[a-z]+:)?//}i.freeze
    FENCED_CODE_BLOCK = /^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$/m.freeze
    DIAGRAM_EXTENSIONS = %w[.mmd .mermaid .puml .plantuml .uml].freeze
    DIAGRAM_SOURCE = /\.(?:mmd|mermaid|puml|plantuml|uml)/i.freeze
    DIAVISUALS_REMOTE = "git@github.com:dosquartsdedocs/diavisuals.git"
    DIAVISUALS_UV_URL = "git+ssh://git@github.com/dosquartsdedocs/diavisuals.git"

    def rewrite(content, site_source:, site_config: {})
      return content if content.nil? || content.empty?

      rewrite_outside_code_fences(content) { |chunk| rewrite_chunk(chunk, site_source: site_source, site_config: site_config) }
    end

    def rewrite_chunk(content, site_source:, site_config: {})
      out = content.dup

      out.gsub!(/!\[([^\]]*)\]\(([^)]*?#{DIAGRAM_SOURCE})(\s+"[^"]*")?\)/i) do
        alt = Regexp.last_match(1)
        path = svg_path_for(Regexp.last_match(2), site_source, site_config: site_config)
        title = Regexp.last_match(3).to_s
        "![#{alt}](#{path}#{title})"
      end

      out.gsub!(/(<img\b[^>]*\bsrc=)(["'])([^"']+?#{DIAGRAM_SOURCE})\2/i) do
        prefix = Regexp.last_match(1)
        quote = Regexp.last_match(2)
        path = svg_path_for(Regexp.last_match(3), site_source, site_config: site_config)
        "#{prefix}#{quote}#{path}#{quote}"
      end

      out
    end

    def rewrite_outside_code_fences(content)
      source = content.to_s
      fences = []
      protected_source = source.gsub(FENCED_CODE_BLOCK) do
        token = "UNALTRAWEBFENCEDCODEBLOCK#{fences.length}"
        fences << Regexp.last_match(0)
        token
      end

      transformed = yield(protected_source)
      fences.each_index.reverse_each do |index|
        transformed.gsub!("UNALTRAWEBFENCEDCODEBLOCK#{index}", fences[index])
      end

      transformed
    end

    def svg_path_for(diagram_path, site_source, site_config: {})
      edited = "#{diagram_path}.edited.svg"
      if local_asset_exists?(edited, site_source)
        warn_when_edited_svg_shadows_newer_source(diagram_path, edited, site_source)
        return edited
      end

      svg_path = "#{diagram_path}.svg"
      render_svg(diagram_path, svg_path, site_source, site_config: site_config)
      svg_path
    end

    def local_asset_exists?(asset_path, site_source)
      local_path = local_asset_path(asset_path, site_source)
      local_path && File.exist?(local_path)
    end

    def local_asset_path(asset_path, site_source)
      local_path = asset_path
        .sub(BASEURL_PREFIX, "")
        .split(/[?#]/, 2)
        .first.to_s
        .sub(%r{\A/+}, "")

      return nil if local_path.empty? || local_path.match?(REMOTE_PATH_PREFIX)

      root = File.expand_path(site_source)
      path = File.expand_path(local_path, root)
      return nil unless path == root || path.start_with?("#{root}/")

      path
    end

    def render_svg(diagram_path, svg_path, site_source, site_config: {})
      return unless render_diagrams?(site_config)

      source_path = local_asset_path(diagram_path, site_source)
      output_path = local_asset_path(svg_path, site_source)
      return unless source_path && output_path && File.file?(source_path)
      return if File.file?(output_path) && File.mtime(output_path) >= File.mtime(source_path)

      command, env = diavisuals_command(site_source, site_config)
      unless command
        warn_once("diavisuals-missing", diavisuals_install_message(site_source))
        return
      end

      FileUtils.mkdir_p(File.dirname(output_path))
      args = [*command, "--project", File.expand_path(site_source), "render-diagram", "--engine", engine_for(source_path), "--format", "svg"]
      args.concat(["--family", diagram_config(site_config)["family"].to_s]) if diagram_config(site_config)["family"].to_s.strip != ""
      profile = diagram_config(site_config)["profile"] || diagram_config(site_config)["compatibility"]
      args.concat(["--profile", profile.to_s]) if profile.to_s.strip != ""
      args.concat([source_path, output_path])

      stdout, stderr, status = Open3.capture3(env || {}, *args, chdir: site_source)
      return if status.success? && File.file?(output_path)

      message = "diavisuals could not render #{diagram_path} to SVG"
      detail = [stderr.to_s.strip, stdout.to_s.strip].reject(&:empty?).join("\n")
      warn_once("diavisuals-render-#{source_path}", detail.empty? ? message : "#{message}: #{detail}")
      raise message if fail_on_render_error?(site_config)
    end

    def warn_when_edited_svg_shadows_newer_source(diagram_path, edited_path, site_source)
      source_path = local_asset_path(diagram_path, site_source)
      edited_local_path = local_asset_path(edited_path, site_source)
      return unless source_path && edited_local_path && File.file?(source_path) && File.file?(edited_local_path)
      return unless File.mtime(source_path) > File.mtime(edited_local_path)

      warn_once(
        "edited-diagram-#{edited_local_path}",
        "#{edited_path} exists and is older than #{diagram_path}; keeping the edited SVG. Ask before replacing it with a regenerated SVG."
      )
    end

    def render_diagrams?(site_config)
      env_value = ENV["UNALTRAWEB_RENDER_DIAGRAMS"].to_s.strip.downcase
      return false if %w[0 false no off].include?(env_value)
      return true if %w[1 true yes on].include?(env_value)

      value = diagram_config(site_config).fetch("render", true)
      ![false, "false", "0", "no", "off"].include?(value)
    end

    def fail_on_render_error?(site_config)
      value = diagram_config(site_config)["fail_on_render_error"]
      [true, "true", "1", "yes", "on"].include?(value)
    end

    def diagram_config(site_config)
      unaltraweb = site_config["unaltraweb"] if site_config.respond_to?(:[])
      diagrams = unaltraweb["diagrams"] if unaltraweb.is_a?(Hash)
      diagrams = site_config["diagrams"] if !diagrams.is_a?(Hash) && site_config.respond_to?(:[])
      diagrams.is_a?(Hash) ? diagrams : {}
    end

    def engine_for(path)
      extension = File.extname(path.to_s).downcase
      return "plantuml" if %w[.puml .plantuml .uml].include?(extension)

      "mermaid"
    end

    def diavisuals_command(site_source, site_config)
      configured = diagram_config(site_config)["diavisuals_command"].to_s.strip
      return [Shellwords.split(configured), nil] unless configured.empty?

      env_command = ENV["DIAVISUALS_COMMAND"].to_s.strip
      return [Shellwords.split(env_command), nil] unless env_command.empty?

      sibling_candidates(site_source).each do |candidate|
        src = File.join(candidate, "src")
        cli = File.join(src, "diavisuals", "cli.py")
        next unless File.file?(cli)

        pythonpath = [src, ENV["PYTHONPATH"]].compact.reject(&:empty?).join(File::PATH_SEPARATOR)
        return [["python3", "-m", "diavisuals.cli"], { "PYTHONPATH" => pythonpath }]
      end

      installed = executable_on_path("diavisuals")
      installed ? [[installed], nil] : [nil, nil]
    end

    def sibling_candidates(site_source)
      root = File.expand_path(site_source)
      core = File.expand_path("..", __dir__)
      [
        File.expand_path("../diavisuals", root),
        File.expand_path("../diavisuals", core)
      ].uniq
    end

    def executable_on_path(name)
      ENV.fetch("PATH", "").split(File::PATH_SEPARATOR).map { |dir| File.join(dir, name) }.find do |path|
        File.executable?(path) && !File.directory?(path)
      end
    end

    def diavisuals_install_message(site_source)
      checkout = File.expand_path("../diavisuals", site_source)
      clone = ["git", "clone", DIAVISUALS_REMOTE, checkout]
      build = ["make", "-C", checkout, "mcp-build"]
      uv = ["uv", "tool", "install", "diavisuals[mcp] @ #{DIAVISUALS_UV_URL}"]
      editable = ["uv", "tool", "install", "--editable", "#{checkout}[mcp]"]
      "diavisuals CLI not found. Install with: #{shell(clone)}; #{shell(build)}. Or use: #{shell(uv)}. Existing checkout: #{shell(editable)}."
    end

    def shell(command)
      command.map { |part| Shellwords.escape(part.to_s) }.join(" ")
    end

    def warn_once(key, message)
      @warnings ||= {}
      return if @warnings[key]

      @warnings[key] = true
      if defined?(Jekyll) && Jekyll.respond_to?(:logger)
        Jekyll.logger.warn("unaltraweb-diagrams:", message)
      else
        warn("unaltraweb-diagrams: #{message}")
      end
    end
  end
end

Jekyll::Hooks.register [:documents, :pages], :pre_render do |doc|
  next unless doc.respond_to?(:content) && doc.content

  doc.content = Unaltraweb::MermaidMmdImages.rewrite(doc.content, site_source: doc.site.source, site_config: doc.site.config)
end if defined?(Jekyll::Hooks)
