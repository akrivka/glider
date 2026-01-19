{
  lib,
  buildNpmPackage,
  nodejs_22,
  makeWrapper,
}:
buildNpmPackage {
  pname = "glider-web";
  version = "0.0.1";

  src = ../../glider-web;

  nodejs = nodejs_22;

  # This hash will need to be updated when package-lock.json changes
  # Run: nix build .#glider-web 2>&1 | grep "got:" to get the new hash
  # Or use: prefetch-npm-deps package-lock.json
  npmDepsHash = "sha256-lKADx5N180GDHOXYifThVRiGdfy95y4XQIKfQu+jnLQ=";

  # Don't run the build script, we'll run the dev server directly
  dontNpmBuild = true;

  nativeBuildInputs = [ makeWrapper ];

  installPhase = ''
    runHook preInstall

    mkdir -p $out/lib/glider-web
    cp -r . $out/lib/glider-web/

    mkdir -p $out/bin
    makeWrapper ${nodejs_22}/bin/npm $out/bin/glider-web \
      --chdir $out/lib/glider-web \
      --add-flags "run dev -- --host 0.0.0.0"

    runHook postInstall
  '';

  meta = with lib; {
    description = "Glider web frontend (SvelteKit dev server)";
    license = licenses.mit;
    platforms = platforms.all;
  };
}
