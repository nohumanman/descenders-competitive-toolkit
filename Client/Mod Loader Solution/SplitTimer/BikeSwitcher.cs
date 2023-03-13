﻿using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using ModLoaderSolution;

namespace SplitTimer
{
	public class BikeSwitcher : MonoBehaviour
	{
        public string oldBike;
        public void ToBike(string bike, string id)
        {
            Debug.Log("ToBike('" + bike + "')");
            StartCoroutine(_ToBike(bike, id));
        }
        IEnumerator _ToBike(string bike, string id)
        {
            GameObject PlayerObject = Utilities.GetPlayerFromId(id);
            if (PlayerObject != null)
            {
                GameObject BikeObject = GetBikeObject(PlayerObject);
                while (BikeObject == null)
                {
                    if (id == (new PlayerIdentification.SteamIntegration()).id.steamID)
                    {
                        BikeObject = GetBikeObject(PlayerObject);
                    }
                    yield return new WaitForEndOfFrame();
                }
                if (!IsDescBike(oldBike) && IsDescBike(bike))
                    yield return DelicatePlayerRespawn(id, PlayerObject, Utilities.GetPlayerInfoImpactFromId(id));
                if (bike == "enduro")
                    gameObject.GetComponent<Utilities>().SetBike(0);
                else if (bike == "downhill")
                    gameObject.GetComponent<Utilities>().SetBike(1);
                else if (bike == "hardtail")
                    gameObject.GetComponent<Utilities>().SetBike(2);
                else
                {
                    if (AssetBundling.Instance.bundle != null)
                    {
                        GameObject bikeReplacement = AssetBundling.Instance.bundle.LoadAsset<GameObject>(bike);
                        if (bike == "BMX")
                        {
                            // rider animations on character_clothed_ragdoll
 
                            Debug.Log("Replacing runtimeAnimatorController");
                            GetPlayerAnim(PlayerObject).runtimeAnimatorController = bikeReplacement.GetComponentInChildren<Animator>().runtimeAnimatorController;

                            foreach (AnimationClip q in GetPlayerAnim(PlayerObject).runtimeAnimatorController.animationClips)
                            {
                                
                            }

                            Animation rider_anims = new Animation();
                            Debug.Log("x12");
                            rider_anims.Stop();
                            Debug.Log("x13");
                            // new rider animations
                            Animation newAnimation = bikeReplacement.GetComponentInChildren<Animation>();
                            Debug.Log("x14");
                            foreach (AnimationClip q in animToAnimStates(newAnimation))
                            {
                                if (q.name == "base")
                                    rider_anims.clip = q;
                                rider_anims.RemoveClip(q.name);
                                rider_anims.AddClip(q, q.name);
                            }
                            rider_anims.Play();
                            /*foreach (BikeAnimation x in FindObjectsOfType<>())
                            {
                                CopyComponent(x, x.gameObject);
                                Destroy(x);
                            }*/
                            // tricsk
                            //Gesture[] gestures = new Gesture[0] { };
                            //string gesturesField = "EL\u0080\u007f\u0084\u0080o";
                            //gestures = (Gesture[])typeof(Cyclist).GetField(gesturesField).GetValue(Utilities.instance.GetPlayer().GetComponent<Cyclist>());
                        }
                        ReplaceBike(
                            bikeReplacement.GetComponentInChildren<SkinnedMeshRenderer>(),
                            bikeReplacement.GetComponent<Animation>(),
                            BikeObject,
                            PlayerObject
                        );
                    }
                    else
                        throw new System.Exception("AssetBundle not loaded! Can't load into specialised demo!!");
                }
                PlayerInf.Instance.OnBikeSwitch(oldBike, bike);
                oldBike = bike;
            }
            
        }
        public Animator GetPlayerAnim(GameObject PlayerObject)
        {
            foreach (Animator a in FindObjectsOfType<Animator>())
            {
                Debug.Log("Anim Root: " + a.transform.root.name);
                Debug.Log("a: " + a.name);
                if (a.name == "character_clothed_ragdoll" && a.transform.root == PlayerObject.transform)
                    return a;
            }
            return null;
        }
        public void ReplaceBike(SkinnedMeshRenderer newSkinnedMeshRenderer, Animation newAnimation, GameObject BikeObject, GameObject PlayerObject)
        {
            BikeObject.GetComponent<SkinnedMeshRenderer>().sharedMesh = newSkinnedMeshRenderer.sharedMesh;
            
            Animation currentBikeAnim = GetBikeModelAnim(PlayerObject);
            if (currentBikeAnim == null)
            {
                Debug.Log("Aaiosjdopiasjdpoajsdopjaspodjaposdjpoasjd==123=1-23=1-293=-1203=-102=3-012=3");
            }
            Debug.Log("bikeObject:" + BikeObject);
            currentBikeAnim.Stop();
            foreach (AnimationClip q in animToAnimStates(newAnimation))
            {
                if (q.name == "base")
                    currentBikeAnim.clip = q;
                currentBikeAnim.RemoveClip(q.name);
                currentBikeAnim.AddClip(q, q.name);
            }
            currentBikeAnim.Play();
            foreach (BikeAnimation x in FindObjectsOfType<BikeAnimation>())
            {
                CopyComponent(x, x.gameObject);
                Destroy(x);
            }
        }
        IEnumerator DelicatePlayerRespawn(string id, GameObject Player, PlayerInfoImpact playerInfoImpact)
        {
            // Player = Utilities.instance.GetPlayer()
            Vector3 pos = Player.transform.position;
            Vector3 rot = Player.transform.eulerAngles;
            Destroy(Player);
            yield return new WaitForSeconds(0.1f);
            FindObjectOfType<PlayerManager>().SpawnPlayerObject(playerInfoImpact);
            yield return new WaitForSeconds(0.1f);
            Utilities.GetPlayerFromId(id).transform.position = pos;
            Utilities.GetPlayerFromId(id).transform.eulerAngles = rot;
            yield return new WaitForSeconds(0.2f);
        }
        bool IsDescBike(string bike)
        {
            // returns true if player was previously on a descenders-own bike
            return bike == "enduro" || bike == "hardtail" || bike == "downhill";
        }
        GameObject GetBikeObject(GameObject PlayerObject)
        {
            foreach (SkinnedMeshRenderer x in FindObjectsOfType<SkinnedMeshRenderer>())
                //if (x.gameObject.name == "bike_downhill_LOD0" && x.gameObject.transform.root.name == "Player_Human")
                if (x.gameObject.name == "bike_downhill_LOD0" && x.gameObject.transform.root == PlayerObject.transform)
                    return x.gameObject;
            return null;
        }
        AnimationClip[] animToAnimStates(Animation anim)
        {
            List<AnimationClip> animStateList = new List<AnimationClip>();
            foreach (AnimationState x in anim)
            {
                AnimationClip clone = Instantiate(x.clip);
                clone.name = x.name;
                animStateList.Add(clone);
            }
            return animStateList.ToArray();
        }
        // stolen from https://answers.unity.com/questions/458207/copy-a-component-at-runtime.html
        Component CopyComponent(Component original, GameObject destination)
        {
            System.Type type = original.GetType();
            Component copy = destination.AddComponent(type);
            // Copied fields can be restricted with BindingFlags
            System.Reflection.FieldInfo[] fields = type.GetFields();
            foreach (System.Reflection.FieldInfo field in fields)
                field.SetValue(copy, field.GetValue(original));
            return copy;
        }
        Animation GetBikeModelAnim(GameObject PlayerObject)
        {
            foreach (Animation a in FindObjectsOfType<Animation>())
            {
                Debug.Log("Anim Root: " + a.transform.root.name);
                if (a.name == "BikeModel" && a.transform.root == PlayerObject.transform)
                    return a;
            }
            return null;
        }
    }
}