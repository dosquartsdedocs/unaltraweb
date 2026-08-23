# frozen_string_literal: true

require "pathname"
require "psych"
require "yaml"

# Rewrites Vega-Lite and Vega specification image references to the single
# generated output declared for the source in .vegavisuals.yml.
module Unaltraweb
  module VegaVisualImages
    module_function

    BASEURL_PREFIX = /\A\{\{\s*site\.baseurl\s*\}\}/.freeze
    REMOTE_PATH_PREFIX = %r{\A(?:[a-z][a-z0-9+.-]*:)?//}i.freeze
    FENCED_CODE_BLOCK = /^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$/m.freeze
    INLINE_CODE_SPAN = /(`+)[^\n]*?\1/.freeze
    VEGA_PATH_SUFFIX = /\.(?:vl|vg)\.json\z/i.freeze
    VEGA_DESTINATION = /(?:\{\{\s*site\.baseurl\s*\}\})?[^\s)"']*?\.(?:vl|vg)\.json(?:[?#][^\s)"']*)?/i.freeze
    OUTPUT_SUFFIXES = %w[.svg .png .pdf].freeze
    SAFE_NAME = /\A[A-Za-z0-9][A-Za-z0-9_.-]*\z/.freeze
    MANIFEST_NAME = ".vegavisuals.yml"

    def rewrite(content, site_source:)
      return content if content.nil? || content.empty?

      rewrite_outside_code_fences(content) { |chunk| rewrite_chunk(chunk, site_source: site_source) }
    end

    def rewrite_chunk(content, site_source:)
      out = content.dup
      out.gsub!(/!\[([^\]]*)\]\((#{VEGA_DESTINATION})(\s+(?:"[^"]*"|'[^']*'))?\)/i) do
        alt = Regexp.last_match(1)
        path = published_path_for(Regexp.last_match(2), site_source)
        title = Regexp.last_match(3).to_s
        "![#{alt}](#{path}#{title})"
      end
      out.gsub!(/(<img\b[^>]*\bsrc=)(["'])([^"']+)\2/i) do
        prefix = Regexp.last_match(1)
        quote = Regexp.last_match(2)
        source_ref = Regexp.last_match(3)
        next Regexp.last_match(0) unless vega_reference?(source_ref)

        "#{prefix}#{quote}#{published_path_for(source_ref, site_source)}#{quote}"
      end
      out
    end

    def rewrite_outside_code_fences(content)
      fences = []
      protected_source = content.to_s.gsub(FENCED_CODE_BLOCK) do
        token = "UNALTRAWEBVEGAVISUALCODE#{fences.length}"
        fences << Regexp.last_match(0)
        token
      end
      protected_source.gsub!(INLINE_CODE_SPAN) do
        token = "UNALTRAWEBVEGAVISUALCODE#{fences.length}"
        fences << Regexp.last_match(0)
        token
      end
      transformed = yield(protected_source)
      fences.each_index.reverse_each do |index|
        transformed.gsub!("UNALTRAWEBVEGAVISUALCODE#{index}", fences[index])
      end
      transformed
    end

    def published_path_for(source_ref, site_source)
      source_path, decoration = reference_parts(source_ref)
      source_relative, = resolve_project_path(
        source_path,
        site_source,
        label: "Vega visualization source",
        must_exist: true
      )
      fatal("Vega visualization source must end in .vl.json or .vg.json: #{source_ref}") unless source_relative.match?(VEGA_PATH_SUFFIX)

      entries = manifest_entries(site_source)
      matches = entries.select { |entry| entry.fetch("source") == source_relative }
      if matches.empty?
        fatal("Vega visualization source is not declared in #{MANIFEST_NAME}: #{source_relative}")
      end
      if matches.length > 1
        fatal("Vega visualization source is ambiguous in #{MANIFEST_NAME}: #{source_relative}")
      end

      output_relative = matches.first.fetch("output")
      if File.extname(output_relative).downcase == ".pdf"
        fatal("Vega visualization output cannot be embedded as a web image: #{output_relative}; use SVG or PNG")
      end
      _, output_local = resolve_project_path(
        output_relative,
        site_source,
        label: "Vega visualization output",
        must_exist: true
      )
      fatal("Missing rendered Vega visualization output: #{output_relative}") unless File.file?(output_local)
      source_root = site_root(site_source)
      unless inside_project?(output_local, source_root)
        fatal("Vega visualization output is outside the Jekyll source directory: #{output_relative}")
      end
      published_relative = Pathname.new(output_local).relative_path_from(Pathname.new(source_root)).to_s

      reference_for(source_ref, published_relative, decoration)
    end

    def manifest_entries(site_source)
      root = project_root(site_source)
      manifest_path = File.join(root, MANIFEST_NAME)
      fatal("Missing required Vega visualization manifest: #{MANIFEST_NAME}") unless File.file?(manifest_path)
      fatal("Vega visualization manifest exceeds 1048576 bytes: #{MANIFEST_NAME}") if File.size(manifest_path) > 1024 * 1024

      text = File.binread(manifest_path).force_encoding(Encoding::UTF_8)
      fatal("Invalid UTF-8 in Vega visualization manifest: #{MANIFEST_NAME}") unless text.valid_encoding?
      reject_unsafe_yaml!(text)
      value = YAML.safe_load(text, permitted_classes: [], permitted_symbols: [], aliases: false)
      fatal("Vega visualization manifest must be a mapping: #{MANIFEST_NAME}") unless value.is_a?(Hash)
      fatal("Vega visualization manifest version must be 1") unless value["version"] == 1
      %w[profile family].each do |field|
        fatal("Vega visualization manifest requires a #{field}") unless value[field].is_a?(String) && !value[field].empty?
      end

      visualizations = value["visualizations"]
      fatal("Vega visualization manifest visualizations must be a list") unless visualizations.is_a?(Array)

      names = {}
      sources = {}
      outputs = {}
      visualizations.each_with_index.map do |item, index|
        fatal("Vega visualization at index #{index} must be a mapping") unless item.is_a?(Hash)
        name = item["name"]
        fatal("Vega visualization at index #{index} has an invalid name") unless name.is_a?(String) && name.match?(SAFE_NAME)
        fatal("Duplicate Vega visualization name: #{name}") if names[name]

        source_relative, source_local = resolve_project_path(
          item["source"],
          root,
          label: "source for Vega visualization #{name}",
          must_exist: true
        )
        output_relative, output_local = resolve_project_path(
          item["output"],
          root,
          label: "output for Vega visualization #{name}",
          must_exist: false
        )
        fatal("Vega visualization #{name} output cannot replace its source") if source_local == output_local
        fatal("Duplicate Vega visualization source: #{source_relative}") if sources[source_relative]
        fatal("Duplicate Vega visualization output: #{output_relative}") if outputs[output_relative]

        output_suffix = File.extname(output_relative).downcase
        fatal("Vega visualization #{name} output must use .svg, .png, or .pdf") unless OUTPUT_SUFFIXES.include?(output_suffix)
        format = item["format"]
        fatal("Vega visualization #{name} format must be a string") unless format.nil? || format.is_a?(String)
        if format && !format.empty? && ".#{format.strip.downcase}" != output_suffix
          fatal("Vega visualization #{name} output suffix does not match format #{format}")
        end
        engine = item.fetch("engine", "auto")
        fatal("Vega visualization #{name} engine must be a string") unless engine.is_a?(String)
        inputs = item.fetch("inputs", [])
        unless inputs.is_a?(Array) && inputs.all? { |entry| entry.is_a?(String) && !entry.empty? }
          fatal("Vega visualization #{name} inputs must be a list of paths")
        end

        names[name] = true
        sources[source_relative] = true
        outputs[output_relative] = true
        { "name" => name, "source" => source_relative, "output" => output_relative }
      end
    rescue Psych::Exception, SystemCallError => e
      fatal("Invalid Vega visualization manifest #{MANIFEST_NAME}: #{e.message}")
    end

    def reject_unsafe_yaml!(text)
      stream = Psych.parse_stream(text)
      fatal("#{MANIFEST_NAME} must contain exactly one YAML document") unless stream.children.length == 1
      inspect_yaml_node!(stream)
    end

    def inspect_yaml_node!(node)
      fatal("YAML aliases are not allowed in #{MANIFEST_NAME}") if node.is_a?(Psych::Nodes::Alias)
      if node.is_a?(Psych::Nodes::Mapping)
        keys = {}
        node.children.each_slice(2) do |key, value|
          fatal("YAML mapping keys must be scalars in #{MANIFEST_NAME}") unless key.is_a?(Psych::Nodes::Scalar)
          fatal("Duplicate YAML key in #{MANIFEST_NAME}: #{key.value}") if keys[key.value]

          keys[key.value] = true
          inspect_yaml_node!(value)
        end
      elsif node.respond_to?(:children)
        Array(node.children).each { |child| inspect_yaml_node!(child) }
      end
    end

    def vega_reference?(source_ref)
      local = source_ref.to_s.sub(BASEURL_PREFIX, "")
      path = local.split(/[?#]/, 2).first.to_s
      path.match?(VEGA_PATH_SUFFIX)
    end

    def reference_parts(source_ref, strict: true)
      local = source_ref.to_s.sub(BASEURL_PREFIX, "")
      match = /\A([^?#]*)([?#].*)?\z/m.match(local)
      return [nil, ""] unless match

      path = match[1]
      decoration = match[2].to_s
      if path.empty? || path.match?(REMOTE_PATH_PREFIX)
        fatal("Vega visualization source must be a local project path: #{source_ref}") if strict
        return [nil, decoration]
      end
      [path.sub(%r{\A/+}, ""), decoration]
    end

    def reference_for(source_ref, relative_path, decoration)
      baseurl = source_ref[BASEURL_PREFIX]
      return "#{baseurl}/#{relative_path}#{decoration}" if baseurl
      return "/#{relative_path}#{decoration}" if source_ref.start_with?("/")

      "{{ site.baseurl }}/#{relative_path}#{decoration}"
    end

    def resolve_project_path(raw, site_source, label:, must_exist:)
      fatal("#{label} must be a non-empty project-relative path") unless raw.is_a?(String) && !raw.strip.empty?
      fatal("#{label} contains a null byte") if raw.include?("\0")
      relative = Pathname.new(raw)
      if relative.absolute? || relative.each_filename.include?("..") || raw.match?(REMOTE_PATH_PREFIX)
        fatal("#{label} must be a safe project-relative path: #{raw}")
      end

      cleaned = relative.cleanpath.to_s
      fatal("#{label} must be a safe project-relative path: #{raw}") if cleaned.empty? || cleaned == "."
      root = project_root(site_source)
      resolved = resolve_location(File.expand_path(cleaned, root))
      fatal("#{label} escapes the project: #{raw}") unless inside_project?(resolved, root)
      fatal("#{label} is not a file: #{raw}") if must_exist && !File.file?(resolved)

      canonical = Pathname.new(resolved).relative_path_from(Pathname.new(root)).to_s
      [canonical, resolved]
    rescue ArgumentError, SystemCallError => e
      fatal("Cannot resolve #{label}: #{raw} (#{e.message})")
    end

    def resolve_location(path)
      return File.realpath(path) if File.exist?(path) || File.symlink?(path)

      missing = []
      cursor = path
      until File.exist?(cursor) || File.symlink?(cursor)
        parent = File.dirname(cursor)
        raise Errno::ENOENT, path if parent == cursor

        missing.unshift(File.basename(cursor))
        cursor = parent
      end
      File.expand_path(File.join(File.realpath(cursor), *missing))
    end

    def project_root(site_source)
      source = site_root(site_source)
      working = File.realpath(Dir.pwd)
      root = inside_project?(source, working) ? working : source
      root
    rescue SystemCallError => e
      fatal("Cannot resolve Vega visualization project root #{site_source}: #{e.message}")
    end

    def site_root(site_source)
      root = File.realpath(site_source)
      fatal("Vega visualization project root is not a directory: #{site_source}") unless File.directory?(root)
      root
    rescue SystemCallError => e
      fatal("Cannot resolve Jekyll source directory #{site_source}: #{e.message}")
    end

    def inside_project?(path, root)
      path == root || path.start_with?("#{root}#{File::SEPARATOR}")
    end

    def fatal(message)
      raise Jekyll::Errors::FatalException, message
    end
  end
end

Jekyll::Hooks.register [:documents, :pages], :pre_render do |doc|
  next unless doc.respond_to?(:content) && doc.content

  doc.content = Unaltraweb::VegaVisualImages.rewrite(doc.content, site_source: doc.site.source)
end if defined?(Jekyll::Hooks)
