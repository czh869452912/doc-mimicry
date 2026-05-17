import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api";
import type { SkillPackResource } from "../../types";

export function useSkillPacks() {
  return useQuery({ queryKey: ["skillPacks"], queryFn: () => api.listSkillPacks() });
}

export function useCreateSkillPack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, title, description }: { id: string; title: string; description: string }) =>
      api.createSkillPack(id, title, description),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["skillPacks"] }),
  });
}

export function useAddSkillPackTextResource(packId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ group, name, content }: { group: SkillPackResource["group"]; name: string; content: string }) => {
      if (!packId) throw new Error("Select a pack before adding resources");
      return api.addSkillPackTextResource(packId, group, name, content);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["skillPacks"] });
      void queryClient.invalidateQueries({ queryKey: ["skillPackResources", packId] });
    },
  });
}

export function useAddSkillPackFileResource(packId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ group, file }: { group: SkillPackResource["group"]; file: File }) => {
      if (!packId) throw new Error("Pack id is required");
      return api.addSkillPackFileResource(packId, group, file);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["skillPacks"] });
      void queryClient.invalidateQueries({ queryKey: ["skillPackResources", packId] });
    },
  });
}

export function useSkillPackResources(packId: string | null) {
  return useQuery({
    queryKey: ["skillPackResources", packId],
    queryFn: () => api.listSkillPackResources(packId ?? ""),
    enabled: Boolean(packId),
  });
}

export function useSkillPackResource(packId: string | null, resourceId: string | null) {
  return useQuery({
    queryKey: ["skillPackResource", packId, resourceId],
    queryFn: () => api.getSkillPackResource(packId ?? "", resourceId ?? ""),
    enabled: Boolean(packId && resourceId),
  });
}

export function useSkillPackArtifact(packId: string | null, path: string) {
  return useQuery({
    queryKey: ["skillPackArtifact", packId, path],
    queryFn: () => api.getSkillPackArtifact(packId ?? "", path),
    enabled: Boolean(packId),
  });
}

export function useUpdateSkillPackArtifact(packId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ path, content, summary }: { path: string; content: string; summary: string }) => {
      if (!packId) throw new Error("Select a pack before editing artifacts");
      return api.updateSkillPackArtifact(packId, path, content, summary);
    },
    onSuccess: (_result, variables) =>
      void queryClient.invalidateQueries({ queryKey: ["skillPackArtifact", packId, variables.path] }),
  });
}

export function useSkillCreatorGeneration(packId: string | null) {
  const queryClient = useQueryClient();
  const [sessionId, setSessionId] = useState<string | null>(null);

  useEffect(() => {
    setSessionId(null);
  }, [packId]);

  return useMutation({
    mutationFn: async (message: string) => {
      if (!packId) throw new Error("Select a pack before running Skill Creator");
      if (sessionId) {
        return api.sendSkillCreatorMessage(packId, sessionId, message);
      }
      const session = await api.createSkillCreatorSession(packId, message);
      setSessionId(session.id);
      return api.generateSkillPack(packId, session.id, message);
    },
    onSuccess: (result) => {
      if (!packId) return;
      for (const path of result.paths) {
        void queryClient.invalidateQueries({ queryKey: ["skillPackArtifact", packId, path] });
      }
    },
  });
}

export function useValidateSkillPack(packId: string | null) {
  return useMutation({
    mutationFn: () => {
      if (!packId) throw new Error("Select a pack before validation");
      return api.validateSkillPack(packId);
    },
  });
}

export function usePublishSkillPack(packId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ note, warnings }: { note: string; warnings: string[] }) => {
      if (!packId) throw new Error("Select a pack before publishing");
      return api.publishSkillPack(packId, note, warnings);
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["skillPacks"] }),
  });
}
