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
  npmDepsHash = "sha256-694AvLJDPvxdqTp1f2Qyt0hsWzWsBEKcDHBfeTI/yos=";

  nativeBuildInputs = [ makeWrapper ];

  installPhase = ''
    runHook preInstall

    mkdir -p $out/lib/glider-web
    cp -r build $out/lib/glider-web/
    cp -r node_modules $out/lib/glider-web/
    cp package.json $out/lib/glider-web/

    mkdir -p $out/bin
    makeWrapper ${nodejs_22}/bin/node $out/bin/glider-web \
      --chdir $out/lib/glider-web \
      --add-flags "build"

    runHook postInstall
  '';

  meta = with lib; {
    description = "Glider web frontend (SvelteKit production server)";
    license = licenses.mit;
    platforms = platforms.all;
  };
}
