# frozen_string_literal: true

require "json"
require "yaml"

# Rewrites Markdown and HTML image references from executable computation
# sources to their declared figure outputs. If an edited SVG exists for the
# declared output, it wins over the generated one.
#
# Authoring model: a chapter references the compute source the same way it
# references a diagram source:
#
#   ![Alt](assets/quarto/figures/boxplot.qmd "Caption"){: data-figure-width="48rem"}
#
# The plugin resolves the source, reads its `unaltraweb_compute.outputs`
# (mode: figure), and rewrites the reference to the first declared output
# (for example `assets/img/data-visualization/boxplot-housing.svg`). An edited
# override named like the output with the extension replaced by `.edited.svg`
# (for example `boxplot-housing.edited.svg`) is preferred and never overwritten.
#
# The plugin never renders: figures are produced by the host computation
# pipeline (`make manual-compute-render`) before Jekyll runs.
module Unaltraweb
  module ComputationFigureImages
    module_function

    BASEURL_PREFIX = /\A\{\{\s*site\.baseurl\s*\}\}/.freeze
    REMOTE_PATH_PREFIX = %r{\A(?:[a-z]+:)?//}i.freeze
    FENCED_CODE_BLOCK = /^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$/m.freeze
    COMPUTE_SUFFIXES = %w[.qmd .rmd .r .py .ipynb].freeze
    COMPUTE_SOURCE = /\.(?:qmd|rmd|ipynb|py|r)(?=[\s)"']|$)/i.freeze
    MEDIA_SUFFIX = /\.(?:gif|jpeg|jpg|pdf|png|svg|webp)\z/i.freeze
    EDITED_SUFFIX = ".edited.svg".freeze

    def rewrite(content, site_source:)
      return content if content.nil? || content.empty?

      rewrite_outside_code_fences(content) { |chunk| rewrite_chunk(chunk, site_source: site_source) }
    end

    def rewrite_chunk(content, site_source:)
      out = content.dup

      out.gsub!(/!\[([^\]]*)\]\(([^)]*?#{COMPUTE_SOURCE})(\s+"[^"]*")?\)/i) do
        alt = Regexp.last_match(1)
        path = published_path_for(Regexp.last_match(2), site_source)
        title = Regexp.last_match(3).to_s
        "![#{alt}](#{path}#{title})"
      end

      out.gsub!(/(<img\b[^>]*\bsrc=)(["'])([^"']+?#{COMPUTE_SOURCE})\2/i) do
        prefix = Regexp.last_match(1)
        quote = Regexp.last_match(2)
        path = published_path_for(Regexp.last_match(3), site_source)
        "#{prefix}#{quote}#{path}#{quote}"
      end

      out
    end

    def rewrite_outside_code_fences(content)
      source = content.to_s
      fences = []
      protected_source = source.gsub(FENCED_CODE_BLOCK) do
        token = "UNALTRAWEBCOMPUTEFIGURECODE#{fences.length}"
        fences << Regexp.last_match(0)
        token
      end

      transformed = yield(protected_source)
      fences.each_index.reverse_each do |index|
        transformed.gsub!("UNALTRAWEBCOMPUTEFIGURECODE#{index}", fences[index])
      end

      transformed
    end

    def published_path_for(source_ref, site_source)
      local = local_asset_path(source_ref, site_source)
      unless local && File.file?(local)
        raise Jekyll::Errors::FatalException, "Computed figure source not found: #{source_ref}. Verify the chapter reference and computation source_roots."
      end

      outputs = declared_outputs(local)
      if outputs.empty?
        warn_once("not-a-figure-#{local}", "Referenced compute source #{source_ref} declares no figure outputs (unaltraweb_compute.mode: figure, outputs); leaving the reference unchanged.")
        return source_ref
      end

      output = outputs.first
      edited = output.sub(MEDIA_SUFFIX, EDITED_SUFFIX)
      edited_local = local_asset_path(edited, site_source)
      if edited_local && File.file?(edited_local)
        warn_when_edited_shadows_newer_source(local, output, edited_local, site_source)
        return reference_for(source_ref, edited)
      end

      output_local = local_asset_path(output, site_source)
      unless output_local && File.file?(output_local)
        raise Jekyll::Errors::FatalException, "Missing rendered figure #{output} for #{source_ref}. Run `make manual-compute-render` (included in `make build`) before building."
      end

      reference_for(source_ref, output)
    end

    def reference_for(source_ref, relative_path)
      baseurl = source_ref[BASEURL_PREFIX]
      return "#{baseurl}/#{relative_path}" if baseurl

      return "/#{relative_path}" if source_ref.start_with?("/")

      relative_path
    end

    def warn_when_edited_shadows_newer_source(source_local, output, edited_local, site_source)
      return unless File.mtime(source_local) > File.mtime(edited_local)

      warn_once(
        "edited-figure-#{edited_local}",
        "#{output.sub(MEDIA_SUFFIX, EDITED_SUFFIX)} exists and is older than #{relative_from(site_source, source_local)}; keeping the edited SVG. Ask before replacing it with a regenerated figure."
      )
    end

    def relative_from(root, path)
      root = File.expand_path(root)
      expanded = File.expand_path(path)
      return path unless expanded.start_with?("#{root}/")

      expanded.delete_prefix("#{root}/")
    end

    def declared_outputs(source_local)
      front = read_front_matter(source_local)
      metadata = front.is_a?(Hash) ? front["unaltraweb_compute"] : nil
      return [] unless metadata.is_a?(Hash)

      mode = metadata["mode"]
      return [] unless mode.to_s.strip.downcase == "figure"

      outputs = metadata["outputs"]
      outputs = [metadata["output"]] if outputs.nil? && metadata["output"]
      return [] unless outputs.is_a?(Array)

      listed = outputs.map(&:to_s).map(&:strip).reject(&:empty?)
      listed.select { |path| path.match?(MEDIA_SUFFIX) && valid_relative_path?(path) }
    end

    def valid_relative_path?(path)
      relative = Pathname.new(path)
      !relative.absolute? && !relative.each_filename.include?("..")
    end

    def read_front_matter(path)
      suffix = File.extname(path.to_s).downcase
      text = suffix == ".qmd" || suffix == ".rmd" ? yaml_front_matter(path) : script_front_matter(path)
      return {} if text.empty?

      YAML.safe_load(text)
    rescue Psych::Exception
      warn_once("invalid-front-matter-#{path}", "Unparseable front matter in #{path}; treating it as a non-figure computation source.")
      {}
    end

    def yaml_front_matter(path)
      match = /\A---\s*\n(.*?)\n---\s*\n?/m.match(File.read(path, encoding: "UTF-8"))
      match ? match[1] : ""
    end

    def script_front_matter(path)
      suffix = File.extname(path.to_s).downcase
      if suffix == ".ipynb"
        return ipynb_front_matter(path) rescue ""
      end

      prefix = suffix == ".r" || suffix == ".rmd" ? "#'" : "#"
      marker = "#{prefix} ---"
      active = false
      block = []
      File.readlines(path, encoding: "UTF-8").each do |line|
        if line.strip == marker
          if active
            return block.join("\n")
          end
          active = true
          next
        end
        block << line.delete_prefix(prefix).sub(/\A /, "") if active
      end
      ""
    end

    def ipynb_front_matter(path)
      notebook = JSON.parse(File.read(path, encoding: "UTF-8"))
      metadata = notebook["metadata"]
      if metadata.is_a?(Hash) && metadata["unaltraweb_front_matter"].is_a?(Hash)
        return YAML.dump(metadata["unaltraweb_front_matter"])
      end
      cells = notebook["cells"] || []
      cells.each do |cell|
        next unless cell["cell_type"] == "markdown" || cell["cell_type"] == "raw"

        source = cell["source"]
        text = source.is_a?(Array) ? source.join : source.to_s
        match = /\A---\s*\n(.*?)\n---\s*\n?/m.match(text)
        return match[1] if match
        break
      end
      ""
    end

    def local_asset_exists?(asset_path, site_source)
      local = local_asset_path(asset_path, site_source)
      local && File.file?(local)
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

    def warn_once(key, message)
      @warnings ||= {}
      return if @warnings[key]

      @warnings[key] = true
      if defined?(Jekyll) && Jekyll.respond_to?(:logger)
        Jekyll.logger.warn("unaltraweb-computations:", message)
      else
        warn("unaltraweb-computations: #{message}")
      end
    end
  end
end

if defined?(Jekyll::Hooks)
  Jekyll::Hooks.register :site, :post_read do |site|
    # Reject generated figure outputs from static files when an edited SVG
    # override exists, so only the authored figure is published.
    site.static_files.reject! do |file|
      relative = file.relative_path.to_s
      next false if relative.empty?
      next false unless relative.match?(Unaltraweb::ComputationFigureImages::MEDIA_SUFFIX)

      edited = relative.sub(Unaltraweb::ComputationFigureImages::MEDIA_SUFFIX, Unaltraweb::ComputationFigureImages::EDITED_SUFFIX)
      local = Unaltraweb::ComputationFigureImages.local_asset_path(edited, site.source)
      local && File.file?(local)
    end
  end
end

Jekyll::Hooks.register [:documents, :pages], :pre_render do |doc|
  next unless doc.respond_to?(:content) && doc.content

  doc.content = Unaltraweb::ComputationFigureImages.rewrite(doc.content, site_source: doc.site.source)
end if defined?(Jekyll::Hooks)