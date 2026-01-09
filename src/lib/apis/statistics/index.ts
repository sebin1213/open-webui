import { WEBUI_API_BASE_URL } from '$lib/constants';

export const getUsageStats = async (
  token: string,
  startDate: string,
  endDate: string,
  page: number = 1,
  size: number = 10,
  options?: {
    startTime?: string;
    endTime?: string;
    team?: string;
    headquarters?: string;
    division?: string;
  }
) => {
  let error: any = null;

  const params = new URLSearchParams({ page: String(page), size: String(size) });
  const res = await fetch(`${WEBUI_API_BASE_URL}/statistics/stats/usage?${params.toString()}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      start_date: startDate,
      end_date: endDate,
      ...(options?.startTime ? { start_time: options.startTime } : {}),
      ...(options?.endTime ? { end_time: options.endTime } : {}),
      ...(options?.team ? { team: options.team } : {}),
      ...(options?.headquarters ? { headquarters: options.headquarters } : {}),
      ...(options?.division ? { division: options.division } : {}),
    }),
  })
    .then(async (res) => {
      if (!res.ok) throw await res.json();
      return res.json();
    })
    .catch((err) => {
      console.error(err);
      error = err;
      return null;
    });

  if (error) throw error;
  return res;
};

export const exportUsageStats = async (
  token: string,
  startDate: string,
  endDate: string,
  options?: {
    startTime?: string;
    endTime?: string;
    team?: string;
    headquarters?: string;
    division?: string;
  }
) => {
  let error: any = null;

  await fetch(`${WEBUI_API_BASE_URL}/statistics/stats/usage/export`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      start_date: startDate,
      end_date: endDate,
      ...(options?.startTime ? { start_time: options.startTime } : {}),
      ...(options?.endTime ? { end_time: options.endTime } : {}),
      ...(options?.team ? { team: options.team } : {}),
      ...(options?.headquarters ? { headquarters: options.headquarters } : {}),
      ...(options?.division ? { division: options.division } : {}),
    }),
  })
    .then(async (response) => {
      if (!response.ok) throw await response.json();
      return response.blob();
    })
    .then((blob) => {
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${startDate}_${endDate}_통계.xlsx`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    })
    .catch((err) => {
      console.error(err);
      error = err?.detail || err?.message || err;
      return null;
    });

  if (error) throw error;
};

export const previewDataCleanup = async (
  token: string,
  cutoffDate: string,
  cutoffTime: string = '23:59:59',
  options?: {
    deleteFiles?: boolean;
    deleteVectors?: boolean;
    deleteDbRecords?: boolean;
  }
) => {
  let error: any = null;

  const res = await fetch(`${WEBUI_API_BASE_URL}/statistics/cleanup/preview`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      cutoff_date: cutoffDate,
      cutoff_time: cutoffTime,
      delete_files: options?.deleteFiles ?? true,
      delete_vectors: options?.deleteVectors ?? true,
      delete_db_records: options?.deleteDbRecords ?? true,
      dry_run: false,
    }),
  })
    .then(async (res) => {
      if (!res.ok) throw await res.json();
      return res.json();
    })
    .catch((err) => {
      console.error(err);
      error = err;
      return null;
    });

  if (error) throw error;
  return res;
};

export const executeDataCleanup = async (
  token: string,
  cutoffDate: string,
  cutoffTime: string = '23:59:59',
  options?: {
    deleteFiles?: boolean;
    deleteVectors?: boolean;
    deleteDbRecords?: boolean;
    dryRun?: boolean;
    confirmPassword?: string;
  }
) => {
  let error: any = null;

  const res = await fetch(`${WEBUI_API_BASE_URL}/statistics/cleanup/execute`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      cutoff_date: cutoffDate,
      cutoff_time: cutoffTime,
      delete_files: options?.deleteFiles ?? true,
      delete_vectors: options?.deleteVectors ?? true,
      delete_db_records: options?.deleteDbRecords ?? true,
      dry_run: options?.dryRun ?? false,
      ...(options?.confirmPassword ? { confirm_password: options.confirmPassword } : {}),
    }),
  })
    .then(async (res) => {
      if (!res.ok) throw await res.json();
      return res.json();
    })
    .catch((err) => {
      console.error(err);
      error = err;
      return null;
    });

  if (error) throw error;
  return res;
};

export const getFileStorageStats = async (
  token: string
) => {
  let error: any = null;

  const res = await fetch(`${WEBUI_API_BASE_URL}/statistics/stats/file-storage`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({}),
  })
    .then(async (res) => {
      if (!res.ok) throw await res.json();
      return res.json();
    })
    .catch((err) => {
      console.error(err);
      error = err;
      return null;
    });

  if (error) throw error;
  return res;
};
