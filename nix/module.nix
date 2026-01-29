{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.services.glider;
  inherit (lib)
    mkEnableOption
    mkOption
    mkIf
    types
    literalExpression
    ;
in
{
  options.services.glider = {
    enable = mkEnableOption "Glider personal data app";

    package = {
      web = mkOption {
        type = types.package;
        description = "Glider web package";
        example = literalExpression "inputs.glider.packages.\${pkgs.system}.glider-web";
      };

      operator = mkOption {
        type = types.package;
        description = "Glider operator (Python worker) package";
        example = literalExpression "inputs.glider.packages.\${pkgs.system}.glider-operator";
      };
    };

    # Network
    host = mkOption {
      type = types.str;
      default = "0.0.0.0";
      description = "Host address for the web frontend";
    };

    port = mkOption {
      type = types.port;
      default = 5173;
      description = "Port for the web frontend";
    };

    # Storage
    dataDir = mkOption {
      type = types.path;
      default = "/var/lib/glider";
      description = "Directory for Glider data and secrets";
    };

    # Secrets
    environmentFile = mkOption {
      type = types.nullOr types.path;
      default = null;
      description = "File with environment variables (OAuth secrets, etc.)";
    };

    # ===== SurrealDB Configuration =====
    surrealdb = {
      enable = mkOption {
        type = types.bool;
        default = true;
        description = "Enable and configure SurrealDB for Glider";
      };

      url = mkOption {
        type = types.str;
        default = "ws://localhost:${toString cfg.surrealdb.port}";
        defaultText = literalExpression ''"ws://localhost:''${toString cfg.surrealdb.port}"'';
        description = "SurrealDB WebSocket URL";
      };

      port = mkOption {
        type = types.port;
        default = 8000;
        description = "SurrealDB port";
      };

      namespace = mkOption {
        type = types.str;
        default = "glider";
        description = "SurrealDB namespace";
      };

      database = mkOption {
        type = types.str;
        default = "glider";
        description = "SurrealDB database name";
      };

      extraFlags = mkOption {
        type = types.listOf types.str;
        default = [ ];
        example = [
          "--user"
          "root"
          "--pass"
          "root"
        ];
        description = "Extra flags to pass to SurrealDB";
      };
    };

  };

  config = mkIf cfg.enable {
    # User and group
    users.users.glider = {
      isSystemUser = true;
      group = "glider";
      home = cfg.dataDir;
      description = "Glider service user";
    };
    users.groups.glider = { };

    # Data directory
    systemd.tmpfiles.rules = [
      "d '${cfg.dataDir}' 0750 glider glider - -"
      "d '${cfg.dataDir}/secrets' 0700 glider glider - -"
    ];

    # ===== SurrealDB =====
    services.surrealdb = mkIf cfg.surrealdb.enable {
      enable = true;
      port = cfg.surrealdb.port;
      extraFlags = cfg.surrealdb.extraFlags;
    };

    # Workaround for sysinfo crate panic in LXC containers
    # https://github.com/NixOS/nixpkgs/issues/441978
    # SurrealDB needs /proc access to read cgroup memory limits
    systemd.services.surrealdb = mkIf cfg.surrealdb.enable {
      serviceConfig = {
        ProcSubset = lib.mkForce "all";
        ProtectProc = lib.mkForce "default";
      };
    };

    # ===== Glider Web Frontend =====
    systemd.services.glider-web = {
      description = "Glider Web Frontend";
      after = [
        "network.target"
      ]
      ++ lib.optional cfg.surrealdb.enable "surrealdb.service"
      ;
      wants =
        lib.optional cfg.surrealdb.enable "surrealdb.service";
      wantedBy = [ "multi-user.target" ];

      serviceConfig = {
        Type = "simple";
        User = "glider";
        Group = "glider";
        WorkingDirectory = cfg.dataDir;
        ExecStart = "${cfg.package.web}/bin/glider-web";
        Restart = "always";
        RestartSec = 5;

        # Security hardening
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        PrivateTmp = true;
        ReadWritePaths = [ cfg.dataDir ];
      }
      // lib.optionalAttrs (cfg.environmentFile != null) {
        EnvironmentFile = cfg.environmentFile;
      };

      environment = {
        HOST = cfg.host;
        PORT = toString cfg.port;
        SURREALDB_URL = cfg.surrealdb.url;
        SURREALDB_NS = cfg.surrealdb.namespace;
        SURREALDB_DB = cfg.surrealdb.database;
      };
    };

    # ===== Glider Worker =====
    systemd.services.glider-worker = {
      description = "Glider Scheduler Worker";
      after = [
        "network.target"
      ]
      ++ lib.optional cfg.surrealdb.enable "surrealdb.service";
      wantedBy = [ "multi-user.target" ];

      serviceConfig = {
        Type = "simple";
        User = "glider";
        Group = "glider";
        WorkingDirectory = cfg.dataDir;
        ExecStart = "${cfg.package.operator}/bin/python -m glider.scheduler";
        Restart = "always";
        RestartSec = 5;

        # Security hardening
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        PrivateTmp = true;
        ReadWritePaths = [ cfg.dataDir ];
      }
      // lib.optionalAttrs (cfg.environmentFile != null) {
        EnvironmentFile = cfg.environmentFile;
      };

      environment = {
        SURREALDB_URL = cfg.surrealdb.url;
        SURREALDB_NS = cfg.surrealdb.namespace;
        SURREALDB_DB = cfg.surrealdb.database;
        GLIDER_SECRETS_DIR = "${cfg.dataDir}/secrets";
        GLIDER_CONFIG_TOML = "${cfg.dataDir}/config.toml";
      };
    };
  };
}
