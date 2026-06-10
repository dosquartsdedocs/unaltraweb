# Make jekyll-cache-bust work when assets live in the unaltraweb gem theme
# instead of the child site repository.
require "jekyll-cache-bust"

module Jekyll
  module CacheBust
    class CacheDigester
      UNALTRAWEB_ROOT = File.expand_path("..", __dir__)

      private

      def directory_files_content
        return main_css_source_content if directory == "assets/_sass"

        target_directory = existing_path(directory)
        return "" unless target_directory

        Dir[File.join(target_directory, "**", "*")].map do |file|
          File.read(file) unless File.directory?(file)
        end.join
      end

      def file_content
        local_file_name = file_name.slice((file_name.index("assets/")..-1))
        return main_css_source_content if local_file_name == "assets/css/main.css"

        target_file = existing_path(local_file_name)
        return "" unless target_file

        File.read(target_file)
      end

      def main_css_source_content
        files = existing_paths("assets/css/main.scss")
        existing_paths("_sass").each do |sass_dir|
          files.concat(Dir[File.join(sass_dir, "**", "*")].reject { |file| File.directory?(file) })
        end
        files.uniq.sort.map { |file| File.read(file) }.join
      end

      def existing_path(relative_path)
        return nil if relative_path.nil? || relative_path.empty?

        existing_paths(relative_path).first
      end

      def existing_paths(relative_path)
        [
          relative_path,
          File.join("docs", relative_path),
          File.join(UNALTRAWEB_ROOT, relative_path),
        ].select { |path| File.exist?(path) }
      end
    end
  end
end
